"""Agent builder module for generating files from Agentfile configuration."""

import json
import shutil
from pathlib import Path
from typing import List

from agentman.agentfile_parser import AgentfileConfig, AgentfileParser
from agentman.frameworks import FastAgentFramework
from agentman.schema_registry import SCHEMA_DIR
from agentman.strict_executor import StrictExecutionEngine


class AgentBuilder:
    """Builds agent files from Agentfile configuration."""

    def __init__(self, config: AgentfileConfig, output_dir: str = "output", source_dir: str = "."):
        self.config = config
        self._output_dir = Path(output_dir)
        self.source_dir = Path(source_dir)
        self.runtime_source_dir = Path(__file__).resolve().parent
        self.copied_stage_schema_names: List[str] = []
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
        execution_plan = self._build_execution_plan()
        self._validate_execution_plan(execution_plan)
        self._copy_prompt_file()
        self._copy_stage_schemas()
        self._copy_runtime_support_files()
        self._generate_python_agent()
        self._generate_config_yaml()
        self._generate_orchestration_manifest()
        self._generate_execution_dag(execution_plan)
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
        self.copied_stage_schema_names = sorted(copied)

    def _copy_runtime_support_files(self):
        """Copy the strict runtime helpers and schemas into the output bundle."""
        for filename in ("strict_executor.py", "agent_registry.py", "schema_registry.py"):
            shutil.copy2(self.runtime_source_dir / filename, self.output_dir / filename)

        schemas_dir = self.output_dir / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)
        for schema_path in SCHEMA_DIR.glob("*.json"):
            shutil.copy2(schema_path, schemas_dir / schema_path.name)

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
                    "role_bindings": orchestrator.role_bindings.to_dict() if orchestrator.role_bindings else None,
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

    def _build_execution_plan(self) -> dict:
        """Construct the strict execution plan from the parsed config."""
        orchestrator = next(
            (item for item in self.config.orchestrators.values() if item.default),
            next(iter(self.config.orchestrators.values()), None),
        )
        if orchestrator is None or orchestrator.role_bindings is None:
            raise ValueError("A strict execution plan requires one orchestrator with role bindings")

        tasks = []
        edges = []
        stages = []
        for stage in orchestrator.stages:
            executor_task = stage.executor_task.to_dict()
            validator_task = stage.validator_task.to_dict()
            tasks.extend([executor_task, validator_task])
            edges.append([executor_task["task_id"], validator_task["task_id"]])
            for dependency_task in executor_task["depends_on_tasks"]:
                edges.append([dependency_task, executor_task["task_id"]])
            stages.append(stage.name)

        stage_transitions = []
        for index, stage_name in enumerate(stages):
            stage_transitions.append(
                {
                    "from_stage": stage_name,
                    "to_stage": stages[index + 1] if index + 1 < len(stages) else None,
                    "gate_condition": "all_checks_passed AND validator_approval",
                    "rollback_on_failure": True,
                }
            )

        return {
            "schema_version": "1.0",
            "role_bindings": orchestrator.role_bindings.to_dict(),
            "execution_plan": {
                "project_id": self.config.source_path or str(self.source_dir),
                "orchestrator": orchestrator.name,
                "stages": stages,
                "tasks": tasks,
                "dag_edges": edges,
                "stage_transitions": stage_transitions,
            },
        }

    def _validate_execution_plan(self, execution_plan: dict) -> None:
        """Validate that the execution plan is enforceable."""
        StrictExecutionEngine.validate_execution_plan(execution_plan)

    def _generate_execution_dag(self, execution_plan: dict) -> None:
        """Generate the machine-readable execution DAG."""
        dag_file = self.output_dir / "execution_dag.json"
        with open(dag_file, "w", encoding="utf-8") as handle:
            json.dump(execution_plan, handle, indent=2, sort_keys=True)
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
            "COPY strict_executor.py .",
            "COPY agent_registry.py .",
            "COPY schema_registry.py .",
            "COPY orchestration.json .",
            "COPY execution_dag.json .",
            "COPY schemas ./schemas",
        ]

        # Add framework-specific configuration files
        framework_config_lines = self.framework.get_dockerfile_config_lines()
        copy_lines.extend(framework_config_lines)

        # Add prompt.txt copy if it exists
        if self.has_prompt_file:
            copy_lines.append("COPY prompt.txt .")
        for schema_name in self.copied_stage_schema_names:
            copy_lines.append(f"COPY {schema_name} .")

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
            "strict_executor.py",
            "agent_registry.py",
            "schema_registry.py",
            "fastagent.config.yaml",
            "fastagent.secrets.yaml",
            "Dockerfile",
            "requirements.txt",
            ".dockerignore",
            "orchestration.json",
            "execution_dag.json",
        }

        missing = sorted(name for name in required_files if not (self.output_dir / name).exists())
        if missing:
            raise ValueError(f"Build output missing required files: {', '.join(missing)}")
        schema_files = {"task_schema.json", "artifact_schema.json"}
        missing_schemas = sorted(
            name for name in schema_files if not (self.output_dir / "schemas" / name).exists()
        )
        if missing_schemas:
            raise ValueError(f"Build output missing required schema files: {', '.join(missing_schemas)}")


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
    print("   - execution_dag.json")
    print("   - strict_executor.py")
    print("   - agent_registry.py")
    print("   - schema_registry.py")
    print("   - Dockerfile")
    print("   - requirements.txt")
    print("   - .dockerignore")

    # Check if prompt.txt was copied
    if builder.has_prompt_file:
        print("   - prompt.txt")

    for schema_name in builder.copied_stage_schema_names:
        print(f"   - {schema_name}")
    print("   - schemas/task_schema.json")
    print("   - schemas/artifact_schema.json")
