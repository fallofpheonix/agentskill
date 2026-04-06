"""Agent builder module for generating files from Agentfile configuration."""

import json
import shutil
from pathlib import Path

from agentman.agentfile_parser import AgentfileConfig, AgentfileParser
from agentman.frameworks import FastAgentFramework


class AgentBuilder:
    """Builds agent files from Agentfile configuration."""

    def __init__(self, config: AgentfileConfig, output_dir: str = "output", source_dir: str = "."):
        self.config = config
        self._output_dir = Path(output_dir)
        self.source_dir = Path(source_dir)
        # Check if prompt.txt exists in the source directory
        self.prompt_file_path = self.source_dir / "prompt.txt"
        self.has_prompt_file = self.prompt_file_path.exists()

        # Initialize framework handler
        self.framework = self._get_framework_handler()

    @property
    def output_dir(self):
        """Get the output directory."""
        return self._output_dir

    @output_dir.setter
    def output_dir(self, value):
        """Set the output directory and update framework handler."""
        self._output_dir = Path(value)
        if hasattr(self, 'framework'):
            self.framework.output_dir = self._output_dir

    def _get_framework_handler(self):
        """Get the appropriate framework handler based on configuration."""
        return FastAgentFramework(self.config, self._output_dir, self.source_dir)

    def build_all(self):
        """Build all generated files."""
        self._ensure_output_dir()
        self._copy_prompt_file()
        self._copy_stage_schemas()
        self._generate_python_agent()
        self._generate_config_yaml()
        self._generate_orchestration_manifest()
        self._generate_dockerfile()
        self._generate_requirements_txt()
        self._generate_dockerignore()
        self._validate_output()

    def _ensure_output_dir(self):
        """Ensure output directory exists."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _copy_prompt_file(self):
        """Copy prompt.txt to output directory if it exists."""
        if self.has_prompt_file:
            dest_path = self.output_dir / "prompt.txt"
            shutil.copy2(self.prompt_file_path, dest_path)

    def _copy_stage_schemas(self):
        """Copy stage schema files into the output directory."""
        copied = set()
        for orchestrator in self.config.orchestrators.values():
            if not orchestrator.stage_schema:
                continue
            source_path = self.source_dir / orchestrator.stage_schema
            if not source_path.exists():
                raise ValueError(f"Stage schema file not found during build: {source_path}")
            if source_path.name in copied:
                continue
            shutil.copy2(source_path, self.output_dir / source_path.name)
            copied.add(source_path.name)

    def _generate_python_agent(self):
        """Generate the main Python agent file."""
        content = self.framework.build_agent_content()

        agent_file = self.output_dir / "agent.py"
        with open(agent_file, 'w', encoding='utf-8') as f:
            f.write(content)

    def _generate_config_yaml(self):
        """Generate the configuration file based on framework."""
        self.framework.generate_config_files()

    def _generate_orchestration_manifest(self):
        """Generate a deterministic manifest for orchestrators and stage contracts."""
        orchestrators = []
        for orchestrator in self.config.orchestrators.values():
            stage_entries = [stage.to_dict() for stage in orchestrator.stages]
            orchestrators.append(
                {
                    "name": orchestrator.name,
                    "agents": orchestrator.agents,
                    "model": orchestrator.model or self.config.default_model,
                    "plan_type": orchestrator.plan_type,
                    "plan_iterations": orchestrator.plan_iterations,
                    "default": orchestrator.default,
                    "stage_schema": orchestrator.stage_schema,
                    "stages": stage_entries,
                }
            )

        manifest = {
            "framework": self.config.framework,
            "default_model": self.config.default_model,
            "orchestrators": orchestrators,
        }

        manifest_file = self.output_dir / "orchestration.json"
        with open(manifest_file, 'w', encoding='utf-8') as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")

    def _generate_dockerfile(self):
        """Generate the Dockerfile."""
        lines = []

        # Start with FROM instruction
        lines.extend([f"FROM {self.config.base_image}", ""])

        # Copy requirements and install Python dependencies
        lines.extend(
            [
                "# Copy requirements and install Python dependencies",
                "COPY requirements.txt .",
                "RUN pip install --no-cache-dir -r requirements.txt",
                "",
            ]
        )

        # Add all other Dockerfile instructions in order (except FROM)
        # We'll handle EXPOSE and CMD at the end in their proper positions
        for instruction in self.config.dockerfile_instructions:
            if instruction.instruction not in ["FROM", "EXPOSE", "CMD"]:
                lines.append(instruction.to_dockerfile_line())

        # Add a blank line if we have custom instructions
        custom_instructions = [
            inst for inst in self.config.dockerfile_instructions if inst.instruction not in ["FROM", "EXPOSE", "CMD"]
        ]
        if custom_instructions:
            lines.append("")

        # Set working directory if not already set by custom instructions
        workdir_set = any(inst.instruction == "WORKDIR" for inst in self.config.dockerfile_instructions)
        if not workdir_set:
            lines.extend(["WORKDIR /app", ""])

        # Copy application files
        copy_lines = [
            "# Copy application files",
            "COPY agent.py .",
        ]

        # Add framework-specific configuration files
        framework_config_lines = self.framework.get_dockerfile_config_lines()
        copy_lines.extend(framework_config_lines)

        # Add prompt.txt copy if it exists
        if self.has_prompt_file:
            copy_lines.append("COPY prompt.txt .")

        copy_lines.append("")
        lines.extend(copy_lines)

        # Add EXPOSE instructions from custom dockerfile instructions first
        expose_instructions = [inst for inst in self.config.dockerfile_instructions if inst.instruction == "EXPOSE"]
        if expose_instructions:
            for instruction in expose_instructions:
                lines.append(instruction.to_dockerfile_line())
            lines.append("")

        # Add EXPOSE from config.expose_ports if not already handled
        if self.config.expose_ports and not expose_instructions:
            expose_lines = [f"EXPOSE {port}" for port in self.config.expose_ports]
            lines.extend(expose_lines)
            lines.append("")

        # Add CMD instructions from custom dockerfile instructions first
        cmd_instructions = [inst for inst in self.config.dockerfile_instructions if inst.instruction == "CMD"]
        if cmd_instructions:
            for instruction in cmd_instructions:
                lines.append(instruction.to_dockerfile_line())
        elif self.config.cmd:
            # Default command from config
            cmd_str = json.dumps(self.config.cmd)
            lines.append(f"CMD {cmd_str}")

        dockerfile = self.output_dir / "Dockerfile"
        with open(dockerfile, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

    def _generate_requirements_txt(self):
        """Generate the requirements.txt file based on framework."""
        requirements = self.framework.get_requirements()

        # Remove duplicates and sort
        requirements = sorted(list(set(requirements)))

        req_file = self.output_dir / "requirements.txt"
        with open(req_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(requirements) + "\n")

    def _generate_dockerignore(self):
        """Generate the .dockerignore file."""
        ignore_patterns = [
            "# Python",
            "__pycache__/",
            "*.py[cod]",
            "*$py.class",
            "*.so",
            ".Python",
            "build/",
            "develop-eggs/",
            "dist/",
            "downloads/",
            "eggs/",
            ".eggs/",
            "lib/",
            "lib64/",
            "parts/",
            "sdist/",
            "var/",
            "wheels/",
            "*.egg-info/",
            ".installed.cfg",
            "*.egg",
            "",
            "# Virtual Environment",
            ".venv",
            "env/",
            "venv/",
            "ENV/",
            "",
            "# IDE",
            ".idea/",
            ".vscode/",
            "*.swp",
            "*.swo",
            "",
            "# Git",
            ".git/",
            ".gitignore",
            "",
            "# Logs",
            "*.log",
            "logs/",
            "",
            "# OS",
            ".DS_Store",
            "Thumbs.db",
        ]

        dockerignore = self.output_dir / ".dockerignore"
        with open(dockerignore, 'w', encoding='utf-8') as f:
            f.write("\n".join(ignore_patterns))

    def _validate_output(self):
        """Validate that all required files were generated."""
        required_files = {
            "agent.py",
            "fastagent.config.yaml",
            "fastagent.secrets.yaml",
            "Dockerfile",
            "requirements.txt",
            ".dockerignore",
            "orchestration.json",
        }

        missing = sorted(name for name in required_files if not (self.output_dir / name).exists())
        if missing:
            raise ValueError(f"Build output missing required files: {', '.join(missing)}")


def build_from_agentfile(agentfile_path: str, output_dir: str = "output") -> None:
    """Build agent files from an Agentfile."""
    parser = AgentfileParser()
    config = parser.parse_file(agentfile_path)

    # Extract source directory from agentfile path
    source_dir = Path(agentfile_path).parent

    builder = AgentBuilder(config, output_dir, source_dir)
    builder.build_all()

    print(f"✅ Generated agent files in {output_dir}/")
    print("   - agent.py")
    print("   - fastagent.config.yaml")
    print("   - fastagent.secrets.yaml")
    print("   - orchestration.json")
    print("   - Dockerfile")
    print("   - requirements.txt")
    print("   - .dockerignore")

    # Check if prompt.txt was copied
    if builder.has_prompt_file:
        print("   - prompt.txt")

    copied_schemas = sorted(
        {
            Path(orchestrator.stage_schema).name
            for orchestrator in config.orchestrators.values()
            if orchestrator.stage_schema
        }
    )
    for schema_name in copied_schemas:
        print(f"   - {schema_name}")
