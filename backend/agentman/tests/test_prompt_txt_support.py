"""Test script to verify prompt.txt support in AgentBuilder."""

import tempfile
from pathlib import Path

from agentman.agent_builder import AgentBuilder
from agentman.agentfile_parser import AgentfileParser


STRICT_STAGE_SCHEMA = """version: 1
roles:
  orchestrator: antigravity
  executor: codex
  validator: opencode
stages:
  - name: analyze_repository
    executor:
      task_id: T_00001_analyze_repository_exec
      agent: codex
      instruction: Build the repository inventory from the tracked tree only.
      timeout_seconds: 3600
      max_retries: 1
      inputs:
        - artifact_key: external:repository
          schema_ref: artifact_schema.json#/definitions/Repository
          source: external
          required: true
      outputs:
        - artifact_key: repo_inventory
          schema_ref: artifact_schema.json#/definitions/RepoInventory
          required: true
    validator:
      task_id: T_00002_analyze_repository_val
      agent: opencode
      inputs:
        - artifact_key: repo_inventory
          schema_ref: artifact_schema.json#/definitions/RepoInventory
          source: stage_output
          required: true
      checks:
        - check_id: C_00001_classification_complete
          check_name: classification_complete
          artifact_key: repo_inventory
          rule: repo_inventory_components_classified
          timeout_seconds: 300
          failure_mode: reject_task
  - name: validate_system
    depends_on:
      - analyze_repository
    executor:
      task_id: T_00003_validate_system_exec
      agent: codex
      instruction: Produce the validation report from the approved repository inventory.
      timeout_seconds: 3600
      max_retries: 1
      inputs:
        - artifact_key: repo_inventory
          schema_ref: artifact_schema.json#/definitions/RepoInventory
          source: stage_output
          required: true
      outputs:
        - artifact_key: validation_report
          schema_ref: artifact_schema.json#/definitions/ValidationReport
          required: true
    validator:
      task_id: T_00004_validate_system_val
      agent: opencode
      inputs:
        - artifact_key: validation_report
          schema_ref: artifact_schema.json#/definitions/ValidationReport
          source: stage_output
          required: true
      checks:
        - check_id: C_00002_tests_pass
          check_name: tests_pass
          artifact_key: validation_report
          rule: validation_report_tests_pass
          timeout_seconds: 300
          failure_mode: reject_task
"""


def test_prompt_txt_support():
    """Test that prompt.txt is copied and integrated when it exists."""

    # Create a test Agentfile content
    agentfile_content = """
FROM yeahdongcn/agentman-base:latest
MODEL anthropic/claude-3-sonnet-20241022

AGENT antigravity
INSTRUCTION Plan the DAG only.
AGENT codex
INSTRUCTION Execute assigned work only.
AGENT opencode
INSTRUCTION Validate assigned outputs only.
ORCHESTRATOR tri_engine
AGENTS antigravity codex opencode
STAGE_SCHEMA stages.yaml

AGENT test_agent
INSTRUCTION You are a helpful test agent.
"""

    # Create temporary directories
    with tempfile.TemporaryDirectory() as temp_source_dir:
        with tempfile.TemporaryDirectory() as temp_output_dir:
            # Create source directory structure
            source_path = Path(temp_source_dir)
            agentfile_path = source_path / "Agentfile"
            prompt_path = source_path / "prompt.txt"
            stages_path = source_path / "stages.yaml"

            # Write Agentfile
            with open(agentfile_path, 'w') as f:
                f.write(agentfile_content)
            stages_path.write_text(STRICT_STAGE_SCHEMA, encoding="utf-8")

            # Write prompt.txt
            prompt_content = "Test prompt content for the agent"
            with open(prompt_path, 'w') as f:
                f.write(prompt_content)

            # Parse the Agentfile
            parser = AgentfileParser()
            config = parser.parse_file(str(agentfile_path))

            # Build with prompt.txt
            builder = AgentBuilder(config, temp_output_dir, temp_source_dir)
            builder.build_all()

            # Verify prompt.txt was copied
            output_prompt_path = Path(temp_output_dir) / "prompt.txt"
            assert output_prompt_path.exists(), "prompt.txt should be copied to output directory"

            with open(output_prompt_path, 'r') as f:
                copied_content = f.read()
            assert copied_content == prompt_content, "prompt.txt content should match"

            # Verify agent.py contains prompt loading logic
            agent_py_path = Path(temp_output_dir) / "agent.py"
            with open(agent_py_path, 'r') as f:
                agent_content = f.read()

            assert "prompt_file = 'prompt.txt'" in agent_content, "Agent should check for prompt.txt"
            assert "with open(prompt_file, 'r', encoding='utf-8') as f:" in agent_content, "Agent should read prompt.txt"
            assert "await agent(prompt_content)" in agent_content, "Agent should use prompt content"

            # Verify Dockerfile contains COPY prompt.txt
            dockerfile_path = Path(temp_output_dir) / "Dockerfile"
            with open(dockerfile_path, 'r') as f:
                dockerfile_content = f.read()

            assert "COPY prompt.txt ." in dockerfile_content, "Dockerfile should copy prompt.txt"
            assert "COPY execution_dag.json ." in dockerfile_content, "Dockerfile should copy execution_dag.json"



def test_no_prompt_txt_backward_compatibility():
    """Test that builds work normally when prompt.txt doesn't exist."""

    # Create a test Agentfile content
    agentfile_content = """
FROM yeahdongcn/agentman-base:latest
MODEL anthropic/claude-3-sonnet-20241022

AGENT antigravity
INSTRUCTION Plan the DAG only.
AGENT codex
INSTRUCTION Execute assigned work only.
AGENT opencode
INSTRUCTION Validate assigned outputs only.
ORCHESTRATOR tri_engine
AGENTS antigravity codex opencode
STAGE_SCHEMA stages.yaml

AGENT test_agent
INSTRUCTION You are a helpful test agent.
"""

    # Create temporary directories
    with tempfile.TemporaryDirectory() as temp_source_dir:
        with tempfile.TemporaryDirectory() as temp_output_dir:
            # Create source directory structure (no prompt.txt)
            source_path = Path(temp_source_dir)
            agentfile_path = source_path / "Agentfile"
            stages_path = source_path / "stages.yaml"

            # Write Agentfile
            with open(agentfile_path, 'w') as f:
                f.write(agentfile_content)
            stages_path.write_text(STRICT_STAGE_SCHEMA, encoding="utf-8")

            # Parse the Agentfile
            parser = AgentfileParser()
            config = parser.parse_file(str(agentfile_path))

            # Build without prompt.txt
            builder = AgentBuilder(config, temp_output_dir, temp_source_dir)
            builder.build_all()

            # Verify prompt.txt was NOT copied
            output_prompt_path = Path(temp_output_dir) / "prompt.txt"
            assert not output_prompt_path.exists(), "prompt.txt should not exist in output directory"

            # Verify agent.py contains standard logic
            agent_py_path = Path(temp_output_dir) / "agent.py"
            with open(agent_py_path, 'r') as f:
                agent_content = f.read()

            assert "prompt_file = 'prompt.txt'" not in agent_content, "Agent should not check for prompt.txt"
            assert "await agent()" in agent_content, "Agent should use standard call"

            # Verify Dockerfile does NOT contain COPY prompt.txt
            dockerfile_path = Path(temp_output_dir) / "Dockerfile"
            with open(dockerfile_path, 'r') as f:
                dockerfile_content = f.read()

            assert "COPY prompt.txt ." not in dockerfile_content, "Dockerfile should not copy prompt.txt"
