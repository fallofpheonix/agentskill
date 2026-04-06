"""
Unit tests for agent_builder module.

Tests cover all aspects of the AgentBuilder including:
- Basic builder functionality
- File generation (Python, YAML, Dockerfile, etc.)
- Output directory management
- Configuration handling
- Secret processing
- Integration with AgentfileConfig
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from agentman.agent_builder import AgentBuilder, build_from_agentfile
from agentman.agentfile_parser import (
    AgentfileConfig,
    MCPServer,
    Agent,
    Orchestrator,
    RoleBindings,
    StageDefinition,
    TaskDefinition,
    TaskExecution,
    TaskValidation,
    ArtifactBinding,
    ValidationCheck,
    SecretValue,
    SecretContext,
)


class TestAgentBuilder:
    """Test suite for AgentBuilder class."""

    def _attach_minimal_runtime(self):
        """Attach a minimal strict orchestrator and task graph to the config."""
        self.config.agents["antigravity"] = Agent("antigravity", instruction="Plan")
        self.config.agents["codex"] = Agent("codex", instruction="Execute")
        self.config.agents["opencode"] = Agent("opencode", instruction="Validate")
        orchestrator = Orchestrator(
            "tri_engine",
            agents=["antigravity", "codex", "opencode"],
            default=True,
            role_bindings=RoleBindings(
                orchestrator="antigravity",
                executor="codex",
                validator="opencode",
            ),
        )
        analyze_exec = TaskDefinition(
            task_id="T_00001_analyze_repository_exec",
            owner_agent="executor",
            assigned_agent="codex",
            stage_name="analyze_repository",
            input_artifacts=[
                ArtifactBinding(
                    artifact_key="external:repository",
                    schema_ref="artifact_schema.json#/definitions/Repository",
                    source="external",
                )
            ],
            output_artifacts=[
                ArtifactBinding(
                    artifact_key="repo_inventory",
                    schema_ref="artifact_schema.json#/definitions/RepoInventory",
                    required=True,
                )
            ],
            execution=TaskExecution(
                instruction="Build the repository inventory from the tracked tree only.",
                timeout_seconds=3600,
                max_retries=1,
            ),
        )
        analyze_val = TaskDefinition(
            task_id="T_00002_analyze_repository_val",
            owner_agent="validator",
            assigned_agent="opencode",
            stage_name="analyze_repository",
            depends_on_tasks=["T_00001_analyze_repository_exec"],
            input_artifacts=[
                ArtifactBinding(
                    artifact_key="repo_inventory",
                    schema_ref="artifact_schema.json#/definitions/RepoInventory",
                    source="stage_output",
                )
            ],
            validation=TaskValidation(
                checks=[
                    ValidationCheck(
                        check_id="C_00001_classification_complete",
                        check_name="classification_complete",
                        artifact_key="repo_inventory",
                        rule="repo_inventory_components_classified",
                        timeout_seconds=300,
                    )
                ]
            ),
        )
        validate_exec = TaskDefinition(
            task_id="T_00003_validate_system_exec",
            owner_agent="executor",
            assigned_agent="codex",
            stage_name="validate_system",
            depends_on_tasks=["T_00002_analyze_repository_val"],
            input_artifacts=[
                ArtifactBinding(
                    artifact_key="repo_inventory",
                    schema_ref="artifact_schema.json#/definitions/RepoInventory",
                    source="stage_output",
                )
            ],
            output_artifacts=[
                ArtifactBinding(
                    artifact_key="validation_report",
                    schema_ref="artifact_schema.json#/definitions/ValidationReport",
                    required=True,
                )
            ],
            execution=TaskExecution(
                instruction="Produce the validation report from the approved repository inventory.",
                timeout_seconds=3600,
                max_retries=1,
            ),
        )
        validate_val = TaskDefinition(
            task_id="T_00004_validate_system_val",
            owner_agent="validator",
            assigned_agent="opencode",
            stage_name="validate_system",
            depends_on_tasks=["T_00003_validate_system_exec"],
            input_artifacts=[
                ArtifactBinding(
                    artifact_key="validation_report",
                    schema_ref="artifact_schema.json#/definitions/ValidationReport",
                    source="stage_output",
                )
            ],
            validation=TaskValidation(
                checks=[
                    ValidationCheck(
                        check_id="C_00002_tests_pass",
                        check_name="tests_pass",
                        artifact_key="validation_report",
                        rule="validation_report_tests_pass",
                        timeout_seconds=300,
                    )
                ]
            ),
        )
        orchestrator.stages = [
            StageDefinition(
                name="analyze_repository",
                executor_task=analyze_exec,
                validator_task=analyze_val,
            ),
            StageDefinition(
                name="validate_system",
                depends_on=["analyze_repository"],
                executor_task=validate_exec,
                validator_task=validate_val,
            ),
        ]
        self.config.orchestrators["tri_engine"] = orchestrator

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AgentfileConfig()
        self.config.base_image = "python:3.11-slim"
        self.config.default_model = "generic.qwen3:latest"
        self.config.cmd = ["python", "agent.py"]
        self._attach_minimal_runtime()

    def test_init_default_output(self):
        """Test builder initialization with default output directory."""
        builder = AgentBuilder(self.config)
        assert builder.config == self.config
        assert builder.output_dir == Path("output")

    def test_init_custom_output(self):
        """Test builder initialization with custom output directory."""
        builder = AgentBuilder(self.config, "custom_output")
        assert builder.config == self.config
        assert builder.output_dir == Path("custom_output")

    def test_ensure_output_dir(self):
        """Test output directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_output"
            builder = AgentBuilder(self.config, str(output_path))

            # Directory should not exist initially
            assert not output_path.exists()

            builder._ensure_output_dir()

            # Directory should exist after calling _ensure_output_dir
            assert output_path.exists()
            assert output_path.is_dir()

    def test_build_python_content_basic(self):
        """Test basic Python content generation."""
        builder = AgentBuilder(self.config)
        content = builder.framework.build_agent_content()

        expected_lines = [
            "import asyncio",
            "from agent_registry import AgentRegistry",
            "from strict_executor import StrictExecutionEngine",
            "from mcp_agent.core.fastagent import FastAgent",
            "",
            "# Create the application",
            'fast = FastAgent("Generated by Agentman")',
            "",
            "def load_execution_plan() -> dict:",
            "async def main() -> None:",
            "    StrictExecutionEngine.validate_execution_plan(load_execution_plan())",
            "    async with fast.run() as agent:",
            "        await agent()",
            "",
            "",
            'if __name__ == "__main__":',
            "    asyncio.run(main())",
        ]

        for line in expected_lines:
            assert line in content

    def test_build_python_content_with_agents(self):
        """Test Python content generation with agents."""
        # Add an agent to the config
        agent = Agent("test_agent")
        agent.instruction = "You are a test assistant"
        agent.servers = ["test_server"]
        self.config.agents["test_agent"] = agent

        builder = AgentBuilder(self.config)
        content = builder.framework.build_agent_content()

        # Should contain agent decorator
        assert "@fast.agent" in content
        assert "test_agent" in content

    def test_build_python_content_with_orchestrators(self):
        """Test Python content generation with orchestrators."""
        # Add an orchestrator to the config
        orchestrator = Orchestrator("test_orchestrator")
        orchestrator.agents = ["agent1", "agent2"]
        self.config.orchestrators["test_orchestrator"] = orchestrator

        builder = AgentBuilder(self.config)
        content = builder.framework.build_agent_content()

        # Should contain orchestrator decorator
        assert "@fast.orchestrator" in content
        assert "test_orchestrator" in content

    def test_generate_config_yaml_basic(self):
        """Test basic config YAML generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder._generate_config_yaml()

            config_file = Path(temp_dir) / "fastagent.config.yaml"
            assert config_file.exists()

            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)

            assert config_data["default_model"] == "generic.qwen3:latest"
            assert "logger" in config_data
            assert config_data["logger"]["level"] == "info"

    def test_generate_config_yaml_with_servers(self):
        """Test config YAML generation with MCP servers."""
        # Add a server to the config
        server = MCPServer("test_server")
        server.command = "uvx"
        server.args = ["mcp-server-test"]
        server.transport = "stdio"
        self.config.servers["test_server"] = server

        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder._generate_config_yaml()

            config_file = Path(temp_dir) / "fastagent.config.yaml"
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)

            assert "mcp" in config_data
            assert "servers" in config_data["mcp"]
            assert "test_server" in config_data["mcp"]["servers"]

    def test_generate_secrets_yaml_simple(self):
        """Test secrets YAML generation with simple secrets."""
        self.config.secrets = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]

        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder.framework.generate_config_files()

            secrets_file = Path(temp_dir) / "fastagent.secrets.yaml"
            assert secrets_file.exists()

            with open(secrets_file, 'r') as f:
                content = f.read()
                # Skip comments to get to YAML content
                yaml_content = []
                for line in content.split('\n'):
                    if not line.startswith('#') and line.strip():
                        yaml_content.append(line)

                if yaml_content:
                    secrets_data = yaml.safe_load('\n'.join(yaml_content))
                    assert "openai" in secrets_data
                    assert "anthropic" in secrets_data

    def test_generate_secrets_yaml_with_values(self):
        """Test secrets YAML generation with secret values."""
        secret_value = SecretValue("TEST_KEY", "test_value")
        self.config.secrets = [secret_value]

        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder.framework.generate_config_files()

            secrets_file = Path(temp_dir) / "fastagent.secrets.yaml"
            assert secrets_file.exists()

    def test_generate_secrets_yaml_with_context(self):
        """Test secrets YAML generation with secret context."""
        secret_context = SecretContext("GENERIC")
        secret_context.values = {"API_KEY": "test_key", "BASE_URL": "http://localhost"}
        self.config.secrets = [secret_context]

        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder.framework.generate_config_files()

            secrets_file = Path(temp_dir) / "fastagent.secrets.yaml"
            assert secrets_file.exists()

            with open(secrets_file, 'r') as f:
                content = f.read()
                # Should contain the context name
                assert "generic" in content.lower()

    # Note: _process_* methods are now internal to framework handlers
    # and tested through integration tests

    def test_generate_dockerfile_custom_base(self):
        """Test Dockerfile generation with custom base image."""
        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder._generate_dockerfile()

            dockerfile = Path(temp_dir) / "Dockerfile"
            assert dockerfile.exists()

            with open(dockerfile, 'r') as f:
                content = f.read()

            assert "FROM python:3.11-slim" in content
            assert "WORKDIR /app" in content
            assert 'CMD ["python", "agent.py"]' in content

    def test_generate_dockerfile_with_expose(self):
        """Test Dockerfile generation with exposed ports."""
        self.config.expose_ports = [8000, 8080]

        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder._generate_dockerfile()

            dockerfile = Path(temp_dir) / "Dockerfile"
            with open(dockerfile, 'r') as f:
                content = f.read()

            assert "EXPOSE 8000" in content
            assert "EXPOSE 8080" in content

    def test_generate_dockerfile_fast_agent_base(self):
        """Test Dockerfile generation with an explicit base image."""
        self.config.base_image = "python:3.12-slim"

        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder._generate_dockerfile()

            dockerfile = Path(temp_dir) / "Dockerfile"
            with open(dockerfile, 'r') as f:
                content = f.read()

            assert "FROM python:3.12-slim" in content
            assert "COPY agent.py" in content
            assert "RUN pip install" in content

    def test_generate_requirements_txt_basic(self):
        """Test basic requirements.txt generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder._generate_requirements_txt()

            req_file = Path(temp_dir) / "requirements.txt"
            assert req_file.exists()

            with open(req_file, 'r') as f:
                content = f.read()

            assert "fast-agent-mcp" in content
            assert "deprecated" in content

    def test_generate_requirements_txt_with_servers(self):
        """Test requirements.txt generation with server dependencies."""
        # Add servers that require additional packages
        server1 = MCPServer("fetch")
        server2 = MCPServer("postgres")
        self.config.servers["fetch"] = server1
        self.config.servers["postgres"] = server2

        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder._generate_requirements_txt()

            req_file = Path(temp_dir) / "requirements.txt"
            with open(req_file, 'r') as f:
                content = f.read()

            assert "requests" not in content
            assert "psycopg2-binary" not in content

    def test_generate_dockerignore(self):
        """Test .dockerignore generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder._generate_dockerignore()

            dockerignore = Path(temp_dir) / ".dockerignore"
            assert dockerignore.exists()

            with open(dockerignore, 'r') as f:
                content = f.read()

            assert "__pycache__/" in content
            assert "*.py[cod]" in content
            assert ".git/" in content
            assert ".DS_Store" in content

    def test_generate_python_agent_file_creation(self):
        """Test that Python agent file is created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder._generate_python_agent()

            agent_file = Path(temp_dir) / "agent.py"
            assert agent_file.exists()

            with open(agent_file, 'r') as f:
                content = f.read()

            assert "import asyncio" in content
            assert "FastAgent" in content

    def test_build_all(self):
        """Test building all files at once."""
        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder.build_all()

            # Check that all expected files are created
            expected_files = [
                "agent.py",
                "strict_executor.py",
                "agent_registry.py",
                "schema_registry.py",
                "fastagent.config.yaml",
                "fastagent.secrets.yaml",
                "orchestration.json",
                "execution_dag.json",
                "Dockerfile",
                "requirements.txt",
                ".dockerignore",
            ]

            for filename in expected_files:
                file_path = Path(temp_dir) / filename
                assert file_path.exists(), f"File {filename} was not created"
            assert (Path(temp_dir) / "schemas" / "task_schema.json").exists()
            assert (Path(temp_dir) / "schemas" / "artifact_schema.json").exists()

    @patch('agentman.agent_builder.AgentfileParser')
    def test_build_from_agentfile(self, mock_parser_class):
        """Test building from Agentfile function."""
        # Mock the parser and its behavior
        mock_parser = mock_parser_class.return_value
        mock_parser.parse_file.return_value = self.config

        with tempfile.TemporaryDirectory() as temp_dir:
            # Call the function
            build_from_agentfile("test_agentfile", temp_dir)

            # Verify parser was called correctly
            mock_parser_class.assert_called_once()
            mock_parser.parse_file.assert_called_once_with("test_agentfile")

            # Check that files were created
            expected_files = [
                "agent.py",
                "strict_executor.py",
                "agent_registry.py",
                "schema_registry.py",
                "fastagent.config.yaml",
                "fastagent.secrets.yaml",
                "orchestration.json",
                "execution_dag.json",
                "Dockerfile",
                "requirements.txt",
                ".dockerignore",
            ]

            for filename in expected_files:
                file_path = Path(temp_dir) / filename
                assert file_path.exists(), f"File {filename} was not created"

    def test_build_from_agentfile_default_output(self):
        """Test building from Agentfile with default output directory."""
        with patch('agentman.agent_builder.AgentfileParser') as mock_parser_class:
            mock_parser = mock_parser_class.return_value
            mock_parser.parse_file.return_value = self.config

            # Mock the AgentBuilder.build_all method to avoid actual file creation
            with patch.object(AgentBuilder, 'build_all') as mock_build_all:
                build_from_agentfile("test_agentfile")

                # Verify the builder was created with default output
                mock_build_all.assert_called_once()

    def test_complex_configuration(self):
        """Test builder with the active configuration surface."""
        # Set up complex configuration
        self.config.default_model = "anthropic/claude-3-sonnet"
        self.config.expose_ports = [8000, 9000]

        # Add server
        server = MCPServer("test_server")
        server.command = "uvx"
        server.args = ["mcp-server-test"]
        server.transport = "stdio"
        self.config.servers["test_server"] = server

        # Add agent
        agent = Agent("test_agent")
        agent.instruction = "You are a test assistant"
        agent.servers = ["test_server"]
        self.config.agents["test_agent"] = agent

        # Add secrets
        self.config.secrets = ["OPENAI_API_KEY", SecretValue("CUSTOM_KEY", "value")]

        with tempfile.TemporaryDirectory() as temp_dir:
            builder = AgentBuilder(self.config, temp_dir)
            builder.build_all()

            # Verify all files are created and contain expected content
            agent_file = Path(temp_dir) / "agent.py"
            with open(agent_file, 'r') as f:
                agent_content = f.read()
            assert "test_agent" in agent_content

            config_file = Path(temp_dir) / "fastagent.config.yaml"
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            assert config_data["default_model"] == "anthropic/claude-3-sonnet"
            assert "test_server" in config_data["mcp"]["servers"]

            dockerfile = Path(temp_dir) / "Dockerfile"
            with open(dockerfile, 'r') as f:
                dockerfile_content = f.read()
            assert "EXPOSE 8000" in dockerfile_content
            assert "EXPOSE 9000" in dockerfile_content


class TestAgentBuilderEdgeCases:
    """Test edge cases and error conditions for AgentBuilder."""

    def test_empty_config(self):
        """An empty config cannot produce a strict execution plan."""
        config = AgentfileConfig()
        builder = AgentBuilder(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            builder.output_dir = Path(temp_dir)
            with pytest.raises(ValueError, match="requires one orchestrator"):
                builder.build_all()

    def test_no_default_model(self):
        """Test builder behavior when no default model is specified."""
        config = AgentfileConfig()
        config.default_model = None
        builder = AgentBuilder(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            builder.output_dir = Path(temp_dir)
            builder._generate_config_yaml()

            config_file = Path(temp_dir) / "fastagent.config.yaml"
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)

            # Should default to "haiku"
            assert config_data["default_model"] == "haiku"

    def test_server_with_env_variables(self):
        """Test server configuration with environment variables."""
        config = AgentfileConfig()

        # Create server with env variables
        server = MCPServer("test_server")
        server.env = {"TEST_VAR1": "placeholder", "TEST_VAR2": "placeholder"}
        config.servers["test_server"] = server
        config.secrets = ["TEST_VAR1"]

        builder = AgentBuilder(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            builder.output_dir = Path(temp_dir)
            builder.framework.generate_config_files()

            secrets_file = Path(temp_dir) / "fastagent.secrets.yaml"
            assert secrets_file.exists()
