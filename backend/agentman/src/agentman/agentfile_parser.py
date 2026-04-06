"""Agentfile parser module for parsing Agentfile configurations."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import yaml


@dataclass
class MCPServer:
    """Represents an MCP server configuration."""

    name: str
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    transport: str = "stdio"
    url: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)

    def to_config_dict(self) -> Dict[str, Any]:
        """Convert to fastagent.config.yaml format."""
        config = {"transport": self.transport}

        if self.command:
            config["command"] = self.command
        if self.args:
            config["args"] = self.args
        if self.url:
            config["url"] = self.url
        if self.env:
            config["env"] = self.env

        return config


@dataclass
class Agent:
    """Represents an agent configuration."""

    name: str
    instruction: str = "You are a helpful agent."
    servers: List[str] = field(default_factory=list)
    model: Optional[str] = None
    use_history: bool = True
    human_input: bool = False
    default: bool = False

    def to_decorator_string(self, default_model: Optional[str] = None) -> str:
        """Generate the @fast.agent decorator string."""
        params = [f'name="{self.name}"', f'instruction="""{self.instruction}"""']

        if self.servers:
            servers_str = "[" + ", ".join(f'"{s}"' for s in self.servers) + "]"
            params.append(f"servers={servers_str}")

        if model_to_use := (self.model or default_model):
            params.append(f'model="{model_to_use}"')

        if not self.use_history:
            params.append("use_history=False")

        if self.human_input:
            params.append("human_input=True")

        if self.default:
            params.append("default=True")

        return "@fast.agent(\n    " + ",\n    ".join(params) + "\n)"


@dataclass
class Orchestrator:
    """Represents an orchestrator workflow."""

    name: str
    agents: List[str] = field(default_factory=list)
    model: Optional[str] = None
    instruction: Optional[str] = None
    plan_type: str = "full"
    plan_iterations: int = 5
    human_input: bool = False
    default: bool = False
    stage_schema: Optional[str] = None
    stages: List["StageDefinition"] = field(default_factory=list)

    def to_decorator_string(self, default_model: Optional[str] = None) -> str:
        """Generate the @fast.orchestrator decorator string."""
        params = []
        params.append(f'name="{self.name}"')

        if self.agents:
            agents_str = "[" + ", ".join(f'"{a}"' for a in self.agents) + "]"
            params.append(f"agents={agents_str}")

        model_to_use = self.model or default_model
        if model_to_use:
            params.append(f'model="{model_to_use}"')

        if self.instruction:
            params.append(f'instruction="""{self.instruction}"""')

        if self.plan_type != "full":
            params.append(f'plan_type="{self.plan_type}"')

        if self.plan_iterations != 5:
            params.append(f"plan_iterations={self.plan_iterations}")

        if self.human_input:
            params.append("human_input=True")

        if self.default:
            params.append("default=True")

        return "@fast.orchestrator(\n    " + ",\n    ".join(params) + "\n)"


@dataclass
class SecretValue:
    """Represents a secret with an inline value."""

    name: str
    value: str


@dataclass
class SecretContext:
    """Represents a secret context that contains multiple key-value pairs."""

    name: str
    values: Dict[str, str] = field(default_factory=dict)


# Type alias for secrets that can be strings, values, or contexts
SecretType = Union[str, SecretValue, SecretContext]


@dataclass
class DockerfileInstruction:
    """Represents a Dockerfile instruction."""

    instruction: str
    args: List[str]

    def to_dockerfile_line(self) -> str:
        """Convert to Dockerfile line format."""
        if self.instruction in ["CMD", "ENTRYPOINT"] and len(self.args) > 1:
            # Handle array format for CMD/ENTRYPOINT
            args_str = json.dumps(self.args)
            return f"{self.instruction} {args_str}"
        return f"{self.instruction} {' '.join(self.args)}"


@dataclass
class StageDefinition:
    """Represents an executable orchestrator stage."""

    name: str
    agent: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    checks: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert stage definition to a serializable dictionary."""
        return asdict(self)


@dataclass
class AgentfileConfig:
    """Represents the complete Agentfile configuration."""

    base_image: str = "python:3.11-slim"
    default_model: Optional[str] = None
    framework: str = "fast-agent"
    servers: Dict[str, MCPServer] = field(default_factory=dict)
    agents: Dict[str, Agent] = field(default_factory=dict)
    orchestrators: Dict[str, Orchestrator] = field(default_factory=dict)
    secrets: List[SecretType] = field(default_factory=list)
    expose_ports: List[int] = field(default_factory=list)
    cmd: List[str] = field(default_factory=lambda: ["python", "agent.py"])
    dockerfile_instructions: List[DockerfileInstruction] = field(default_factory=list)
    source_path: Optional[str] = None


class AgentfileParser:
    """Parser for Agentfile format."""

    def __init__(self):
        self.config = AgentfileConfig()
        self.current_context = None
        self.current_item = None

    def parse_file(self, filepath: str) -> AgentfileConfig:
        """Parse an Agentfile and return the configuration."""
        path = Path(filepath).resolve()
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return self.parse_content(content, base_dir=path.parent, source_path=str(path))

    def parse_content(
        self,
        content: str,
        base_dir: Optional[Path] = None,
        source_path: Optional[str] = None,
    ) -> AgentfileConfig:
        """Parse Agentfile content and return the configuration."""
        self.config = AgentfileConfig()
        self.current_context = None
        self.current_item = None
        self.config.source_path = source_path

        lines = content.split('\n')

        # Pre-process lines to handle multi-line continuations with backslash
        processed_lines = []
        current_line = ""
        continued_start_line_num = None

        for line_num, line in enumerate(lines, 1):
            line = line.rstrip()  # Remove trailing whitespace but keep leading

            # Skip empty lines and comments if not part of a continuation
            if not current_line and (not line or line.lstrip().startswith('#')):
                continue

            # Check for line continuation
            if line.endswith('\\'):
                # Remove the backslash and add to current line with a space
                if not current_line:
                    # This is the start of a new continued line, so record the starting line number
                    continued_start_line_num = line_num
                current_line += f"{line[:-1].rstrip()} "
            else:
                # Complete the line
                current_line += line
                if current_line.strip():  # Only add non-empty lines
                    # Use the real start line number for continued instructions
                    if continued_start_line_num is not None:
                        processed_lines.append((continued_start_line_num, current_line.strip()))
                        continued_start_line_num = None
                    else:
                        processed_lines.append((line_num, current_line.strip()))
                current_line = ""

        # Handle any remaining line (shouldn't happen with proper syntax)
        if current_line.strip():
            # Use the real start line number for continued instructions if present
            if continued_start_line_num is not None:
                processed_lines.append((continued_start_line_num, current_line.strip()))
            else:
                processed_lines.append((len(lines), current_line.strip()))

        # Parse each processed line
        for line_num, line in processed_lines:
            try:
                self._parse_line(line)
            except Exception as e:
                raise ValueError(f"Error parsing line {line_num}: {line}\n{str(e)}") from e

        self._validate_config(base_dir)
        return self.config

    def _parse_line(self, line: str):
        """Parse a single line of the Agentfile."""
        # Split by whitespace but handle quoted strings
        parts = self._split_respecting_quotes(line)
        if not parts:
            return

        instruction = parts[0].upper()

        # Agentman-specific instructions (not Docker)
        if instruction == "MODEL":
            # Check if we're in a context that should handle MODEL as sub-instruction
            if self.current_context in ["agent", "orchestrator"]:
                self._handle_sub_instruction(instruction, parts)
            else:
                self._handle_model(parts)
        elif instruction == "FRAMEWORK":
            self._handle_framework(parts)
        elif instruction in ["SERVER", "MCP_SERVER"]:
            self._handle_server(parts)
        elif instruction == "AGENT":
            self._handle_agent(parts)
        elif instruction == "ROUTER":
            raise ValueError("ROUTER is not supported in the minimal tri-engine runtime")
        elif instruction == "CHAIN":
            raise ValueError("CHAIN is not supported in the minimal tri-engine runtime")
        elif instruction == "ORCHESTRATOR":
            self._handle_orchestrator(parts)
        elif instruction == "SECRET":
            self._handle_secret(parts)
        # Dockerfile instructions - handle specially where needed
        elif instruction == "FROM":
            self._handle_from(parts)
            self._handle_dockerfile_instruction(instruction, parts)
        elif instruction == "EXPOSE":
            self._handle_expose(parts)
            self._handle_dockerfile_instruction(instruction, parts)
        elif instruction == "CMD":
            self._handle_cmd(parts)
            # Store the CMD instruction with the correctly parsed args
            dockerfile_instruction = DockerfileInstruction(instruction="CMD", args=self.config.cmd)
            self.config.dockerfile_instructions.append(dockerfile_instruction)
        elif instruction == "RUN":
            self._handle_dockerfile_instruction(instruction, parts)
        # All other Dockerfile instructions - store as-is
        elif instruction in [
            # Standard Dockerfile instructions
            "ARG",
            "ADD",
            "COPY",
            "ENTRYPOINT",
            "HEALTHCHECK",
            "LABEL",
            "MAINTAINER",
            "ONBUILD",
            "SHELL",
            "STOPSIGNAL",
            "USER",
            "VOLUME",
            "WORKDIR",
            # BuildKit instructions
            "MOUNT",
            "BUILDKIT",
        ]:
            self._handle_dockerfile_instruction(instruction, parts)
        # Sub-instructions for contexts
        elif instruction in [
            "COMMAND",
            "ARGS",
            "INSTRUCTION",
            "SERVERS",
            "AGENTS",
            "STAGE_SCHEMA",
            "TRANSPORT",
            "URL",
            "USE_HISTORY",
            "HUMAN_INPUT",
            "PLAN_TYPE",
            "PLAN_ITERATIONS",
            "API_KEY",
            "BASE_URL",
            "DEFAULT",
        ]:
            self._handle_sub_instruction(instruction, parts)
        # Handle ENV - could be Dockerfile instruction or sub-instruction
        elif instruction == "ENV":
            if self.current_context and self.current_context == "server":
                # It's a sub-instruction for SERVER context
                self._handle_sub_instruction(instruction, parts)
            else:
                # It's a Dockerfile instruction
                self._handle_dockerfile_instruction(instruction, parts)
        else:
            if self.current_context == "secret":
                self._handle_secret_sub_instruction(instruction, parts)
            elif self.current_context:
                raise ValueError(f"Unsupported {self.current_context.upper()} sub-instruction: {instruction}")
            else:
                # Unknown top-level instructions are preserved as Dockerfile lines
                # for forward compatibility with the container surface.
                self._handle_dockerfile_instruction(instruction, parts)

    def _split_respecting_quotes(self, line: str) -> List[str]:
        """Split line by whitespace but respect quoted strings."""
        parts = []
        current = ""
        in_quotes = False
        quote_char = None

        i = 0
        while i < len(line):
            char = line[i]

            if not in_quotes and char in ['"', "'"]:
                in_quotes = True
                quote_char = char
                current += char
            elif in_quotes and char == quote_char:
                in_quotes = False
                quote_char = None
                current += char
            elif not in_quotes and char.isspace():
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += char
            i += 1

        if current:
            parts.append(current)

        return parts

    def _unquote(self, s: str) -> str:
        """Remove quotes from a string if present."""
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ['"', "'"]:
            return s[1:-1]
        return s

    def _handle_from(self, parts: List[str]):
        """Handle FROM instruction."""
        if len(parts) < 2:
            raise ValueError("FROM requires a base image")
        self.config.base_image = self._unquote(parts[1])
        self.current_context = None

    def _handle_model(self, parts: List[str]):
        """Handle MODEL instruction."""
        if len(parts) < 2:
            raise ValueError("MODEL requires a model name")
        self.config.default_model = self._unquote(parts[1])
        self.current_context = None

    def _handle_framework(self, parts: List[str]):
        """Handle FRAMEWORK instruction."""
        if len(parts) < 2:
            raise ValueError("FRAMEWORK requires a framework name")
        framework = self._unquote(parts[1]).lower()
        if framework != "fast-agent":
            raise ValueError(f"Unsupported framework: {framework}. Supported: fast-agent")
        self.config.framework = framework
        self.current_context = None

    def _handle_server(self, parts: List[str]):
        """Handle SERVER instruction."""
        if len(parts) < 2:
            raise ValueError("SERVER requires a server name")
        name = self._unquote(parts[1])
        self.config.servers[name] = MCPServer(name=name)
        self.current_context = "server"
        self.current_item = name

    def _handle_agent(self, parts: List[str]):
        """Handle AGENT instruction."""
        if len(parts) < 2:
            raise ValueError("AGENT requires an agent name")
        name = self._unquote(parts[1])
        self.config.agents[name] = Agent(name=name)
        self.current_context = "agent"
        self.current_item = name

    def _handle_orchestrator(self, parts: List[str]):
        """Handle ORCHESTRATOR instruction."""
        if len(parts) < 2:
            raise ValueError("ORCHESTRATOR requires an orchestrator name")
        name = self._unquote(parts[1])
        self.config.orchestrators[name] = Orchestrator(name=name)
        self.current_context = "orchestrator"
        self.current_item = name

    def _handle_secret(self, parts: List[str]):
        """Handle SECRET instruction.

        Supports multiple formats:
        - SECRET ANTHROPIC_API_KEY (simple reference)
        - SECRET ANTHROPIC_API_KEY <<real_api_key>> (inline value)
        - SECRET openai (context for multiple values)
        """
        if len(parts) < 2:
            raise ValueError("SECRET requires a secret name")

        secret_name = self._unquote(parts[1])

        # Check if it's an inline value: SECRET KEY value
        if len(parts) >= 3:
            value = ' '.join(parts[2:])  # Join all remaining parts as the value
            secret = SecretValue(name=secret_name, value=self._unquote(value))
            self.config.secrets.append(secret)
            self.current_context = None
        # Check if it's a context (no value, will be populated with sub-instructions)
        elif len(parts) == 2:
            # Check if a secret context with this name already exists
            existing_secret = next(
                (
                    secret
                    for secret in self.config.secrets
                    if isinstance(secret, SecretContext) and secret.name == secret_name
                ),
                None,
            )

            if existing_secret:
                # Reuse existing secret context
                self.current_context = "secret"
                self.current_item = secret_name
            else:
                # Create a new secret context - this will be used if subsequent
                # lines contain key-value pairs. If no key-value pairs follow,
                # it will be treated as a simple reference
                secret = SecretContext(name=secret_name)
                self.config.secrets.append(secret)
                self.current_context = "secret"
                self.current_item = secret_name
        else:
            raise ValueError("Invalid SECRET format. Use: SECRET NAME or SECRET NAME value")

    def _handle_secret_sub_instruction(self, instruction: str, parts: List[str]):
        """Handle sub-instructions for SECRET context (key-value pairs)."""
        if not self.current_item:
            raise ValueError("SECRET sub-instruction without active secret context")

        # Find the current secret context
        secret_context = None
        for secret in self.config.secrets:
            if isinstance(secret, SecretContext) and secret.name == self.current_item:
                secret_context = secret
                break

        if not secret_context:
            raise ValueError(f"Secret context {self.current_item} not found")

        # Handle key-value pairs like: API_KEY your_key_here
        if len(parts) >= 2:
            key = instruction.upper()
            value = ' '.join(parts[1:])
            secret_context.values[key] = self._unquote(value)
        else:
            raise ValueError("SECRET context requires KEY VALUE format")

    def _handle_expose(self, parts: List[str]):
        """Handle EXPOSE instruction."""
        if len(parts) < 2:
            raise ValueError("EXPOSE requires a port number")
        try:
            port = int(parts[1])
            if port not in self.config.expose_ports:
                self.config.expose_ports.append(port)
        except ValueError as exc:
            raise ValueError(f"Invalid port number: {parts[1]}") from exc
        self.current_context = None

    def _handle_cmd(self, parts: List[str]):
        """Handle CMD instruction."""
        if len(parts) < 2:
            raise ValueError("CMD requires at least one argument")
        # Handle both array format and simple format
        if parts[1].startswith('[') and parts[-1].endswith(']'):
            # Array format: CMD ["python", "agent.py"]
            cmd_str = ' '.join(parts[1:])
            # Simple JSON-like parsing
            cmd_str = cmd_str.strip('[]')
            self.config.cmd = [self._unquote(item.strip()) for item in cmd_str.split(',')]
        else:
            # Simple format: CMD python agent.py
            self.config.cmd = [self._unquote(part) for part in parts[1:]]
        self.current_context = None

    def _handle_dockerfile_instruction(self, instruction: str, parts: List[str]):
        """Handle any generic Dockerfile instruction."""
        if len(parts) < 2:
            raise ValueError(f"{instruction} requires arguments")

        # Special handling for ENV instruction to support KEY=VALUE format
        if instruction == "ENV":
            # Handle both KEY VALUE and KEY=VALUE formats for Dockerfile ENV
            args = parts[1:]
            if len(args) == 1 and '=' in args[0]:
                # KEY=VALUE format - keep as single argument for Dockerfile
                dockerfile_args = args
            else:
                # KEY VALUE format or multiple args - keep as is
                dockerfile_args = args
        else:
            dockerfile_args = parts[1:]

        # Store all instructions for ordered generation
        dockerfile_instruction = DockerfileInstruction(instruction=instruction, args=dockerfile_args)
        self.config.dockerfile_instructions.append(dockerfile_instruction)
        self.current_context = None

    def _handle_sub_instruction(self, instruction: str, parts: List[str]):
        """Handle sub-instructions that modify the current context item."""
        if not self.current_context:
            # Special case: if we're not in a context but this looks like
            # a key-value pair for a secret context, try to handle it
            if self.current_item and any(
                isinstance(s, SecretContext) and s.name == self.current_item for s in self.config.secrets
            ):
                self.current_context = "secret"
                self._handle_secret_sub_instruction(instruction, parts)
                return
            raise ValueError(f"{instruction} can only be used within a context (SERVER, AGENT, etc.)")

        if self.current_context == "server":
            self._handle_server_sub_instruction(instruction, parts)
        elif self.current_context == "agent":
            self._handle_agent_sub_instruction(instruction, parts)
        elif self.current_context == "orchestrator":
            self._handle_orchestrator_sub_instruction(instruction, parts)
        elif self.current_context == "secret":
            self._handle_secret_sub_instruction(instruction, parts)

    def _handle_server_sub_instruction(self, instruction: str, parts: List[str]):
        """Handle sub-instructions for SERVER context."""
        server = self.config.servers[self.current_item]

        if instruction == "COMMAND":
            if len(parts) < 2:
                raise ValueError("COMMAND requires a command")
            server.command = self._unquote(parts[1])
        elif instruction == "ARGS":
            if len(parts) < 2:
                raise ValueError("ARGS requires at least one argument")
            server.args = [self._unquote(part) for part in parts[1:]]
        elif instruction == "TRANSPORT":
            if len(parts) < 2:
                raise ValueError("TRANSPORT requires a transport type")
            transport = self._unquote(parts[1])
            if transport not in ["stdio", "sse", "http"]:
                raise ValueError(f"Invalid transport type: {transport}")
            server.transport = transport
        elif instruction == "URL":
            if len(parts) < 2:
                raise ValueError("URL requires a URL")
            server.url = self._unquote(parts[1])
        elif instruction == "ENV":
            if len(parts) < 2:
                raise ValueError("ENV requires KEY VALUE or KEY=VALUE")

            if len(parts) == 2:
                # Handle KEY=VALUE format
                env_part = parts[1]
                if '=' in env_part:
                    key, value = env_part.split('=', 1)  # Split only on first =
                    key = self._unquote(key)
                    value = self._unquote(value)
                    server.env[key] = value
                else:
                    raise ValueError("ENV requires KEY VALUE or KEY=VALUE")
            elif len(parts) >= 3:
                # Handle KEY VALUE format
                key = self._unquote(parts[1])
                value = self._unquote(' '.join(parts[2:]))  # Join remaining parts as value
                server.env[key] = value
            else:
                raise ValueError("ENV requires KEY VALUE or KEY=VALUE")
        else:
            raise ValueError(f"Unsupported SERVER sub-instruction: {instruction}")

    def _handle_agent_sub_instruction(self, instruction: str, parts: List[str]):
        """Handle sub-instructions for AGENT context."""
        agent = self.config.agents[self.current_item]

        if instruction == "INSTRUCTION":
            if len(parts) < 2:
                raise ValueError("INSTRUCTION requires instruction text")
            agent.instruction = self._unquote(' '.join(parts[1:]))
        elif instruction == "SERVERS":
            if len(parts) < 2:
                raise ValueError("SERVERS requires at least one server name")
            agent.servers = [self._unquote(part) for part in parts[1:]]
        elif instruction == "MODEL":
            if len(parts) < 2:
                raise ValueError("MODEL requires a model name")
            agent.model = self._unquote(parts[1])
        elif instruction == "USE_HISTORY":
            if len(parts) < 2:
                raise ValueError("USE_HISTORY requires true/false")
            agent.use_history = self._unquote(parts[1]).lower() in ['true', '1', 'yes']
        elif instruction == "HUMAN_INPUT":
            if len(parts) < 2:
                raise ValueError("HUMAN_INPUT requires true/false")
            agent.human_input = self._unquote(parts[1]).lower() in ['true', '1', 'yes']
        elif instruction == "DEFAULT":
            if len(parts) < 2:
                raise ValueError("DEFAULT requires true/false")
            agent.default = self._unquote(parts[1]).lower() in ['true', '1', 'yes']
        else:
            raise ValueError(f"Unsupported AGENT sub-instruction: {instruction}")

    def _handle_orchestrator_sub_instruction(self, instruction: str, parts: List[str]):
        """Handle sub-instructions for ORCHESTRATOR context."""
        orchestrator = self.config.orchestrators[self.current_item]

        if instruction == "AGENTS":
            if len(parts) < 2:
                raise ValueError("AGENTS requires at least one agent name")
            orchestrator.agents = [self._unquote(part) for part in parts[1:]]
        elif instruction == "MODEL":
            if len(parts) < 2:
                raise ValueError("MODEL requires a model name")
            orchestrator.model = self._unquote(parts[1])
        elif instruction == "INSTRUCTION":
            if len(parts) < 2:
                raise ValueError("INSTRUCTION requires instruction text")
            orchestrator.instruction = self._unquote(' '.join(parts[1:]))
        elif instruction == "PLAN_TYPE":
            if len(parts) < 2:
                raise ValueError("PLAN_TYPE requires a plan type")
            plan_type = self._unquote(parts[1])
            if plan_type not in ["full", "iterative"]:
                raise ValueError(f"Invalid plan type: {plan_type}")
            orchestrator.plan_type = plan_type
        elif instruction == "PLAN_ITERATIONS":
            if len(parts) < 2:
                raise ValueError("PLAN_ITERATIONS requires a number")
            try:
                orchestrator.plan_iterations = int(parts[1])
            except ValueError as exc:
                raise ValueError(f"Invalid number for PLAN_ITERATIONS: {parts[1]}") from exc
        elif instruction == "HUMAN_INPUT":
            if len(parts) < 2:
                raise ValueError("HUMAN_INPUT requires true/false")
            orchestrator.human_input = self._unquote(parts[1]).lower() in ['true', '1', 'yes']
        elif instruction == "DEFAULT":
            if len(parts) < 2:
                raise ValueError("DEFAULT requires true/false")
            orchestrator.default = self._unquote(parts[1]).lower() in ['true', '1', 'yes']
        elif instruction == "STAGE_SCHEMA":
            if len(parts) < 2:
                raise ValueError("STAGE_SCHEMA requires a file path")
            orchestrator.stage_schema = self._unquote(parts[1])
        else:
            raise ValueError(f"Unsupported ORCHESTRATOR sub-instruction: {instruction}")

    def _validate_config(self, base_dir: Optional[Path]) -> None:
        """Validate cross-reference integrity for the parsed configuration."""
        self._validate_agent_servers()
        self._validate_orchestrator_references(base_dir)

    def _validate_agent_servers(self) -> None:
        """Ensure each referenced server exists."""
        for agent in self.config.agents.values():
            missing = [server for server in agent.servers if server not in self.config.servers]
            if missing:
                raise ValueError(f"Agent {agent.name} references undefined servers: {', '.join(missing)}")

    def _validate_orchestrator_references(self, base_dir: Optional[Path]) -> None:
        """Validate orchestrator references and load structured stage schemas."""
        default_orchestrators = [name for name, item in self.config.orchestrators.items() if item.default]
        if len(default_orchestrators) > 1:
            raise ValueError("Only one orchestrator can be marked DEFAULT true")

        for orchestrator in self.config.orchestrators.values():
            missing_agents = [agent for agent in orchestrator.agents if agent not in self.config.agents]
            if missing_agents:
                raise ValueError(
                    f"Orchestrator {orchestrator.name} references undefined agents: {', '.join(missing_agents)}"
                )
            if orchestrator.stage_schema:
                orchestrator.stages = self._load_stage_schema(orchestrator, base_dir)

    def _load_stage_schema(self, orchestrator: Orchestrator, base_dir: Optional[Path]) -> List[StageDefinition]:
        """Load and validate an orchestrator stage schema."""
        if base_dir is None:
            raise ValueError(f"Orchestrator {orchestrator.name} requires a file-backed parse for STAGE_SCHEMA")

        schema_path = (base_dir / orchestrator.stage_schema).resolve()
        if not schema_path.exists():
            raise ValueError(f"Stage schema not found: {schema_path}")

        with open(schema_path, 'r', encoding='utf-8') as handle:
            raw = yaml.safe_load(handle) or {}

        if not isinstance(raw, dict):
            raise ValueError(f"Stage schema must be a mapping: {schema_path}")

        raw_stages = raw.get("stages")
        if not isinstance(raw_stages, list) or not raw_stages:
            raise ValueError(f"Stage schema {schema_path} must define a non-empty 'stages' list")

        stages: List[StageDefinition] = []
        seen_stage_names: Set[str] = set()
        produced_artifacts: Dict[str, str] = {}

        for index, item in enumerate(raw_stages, start=1):
            stage = self._parse_stage_definition(item, index)
            if stage.name in seen_stage_names:
                raise ValueError(f"Duplicate stage name in {schema_path}: {stage.name}")
            if stage.agent not in orchestrator.agents:
                raise ValueError(
                    f"Stage {stage.name} uses agent {stage.agent} outside orchestrator {orchestrator.name}"
                )
            if stage.agent not in self.config.agents:
                raise ValueError(f"Stage {stage.name} references undefined agent {stage.agent}")
            invalid_dependencies = [name for name in stage.depends_on if name not in seen_stage_names]
            if invalid_dependencies:
                raise ValueError(
                    f"Stage {stage.name} has invalid depends_on entries: {', '.join(invalid_dependencies)}"
                )

            internal_inputs = [artifact for artifact in stage.inputs if not artifact.startswith("external:")]
            unresolved_inputs = [artifact for artifact in internal_inputs if artifact not in produced_artifacts]
            if unresolved_inputs:
                raise ValueError(
                    f"Stage {stage.name} requires artifacts not produced earlier: {', '.join(unresolved_inputs)}"
                )

            dependency_closure = self._resolve_stage_dependencies(stages, stage.depends_on)
            for artifact in internal_inputs:
                producer = produced_artifacts[artifact]
                if producer not in dependency_closure:
                    raise ValueError(
                        f"Stage {stage.name} consumes artifact {artifact} from {producer} without depending on it"
                    )

            for artifact in stage.outputs:
                if artifact.startswith("external:"):
                    raise ValueError(f"Stage {stage.name} output cannot use reserved external: prefix")
                if artifact in produced_artifacts:
                    raise ValueError(
                        f"Artifact {artifact} is produced by both {produced_artifacts[artifact]} and {stage.name}"
                    )
                produced_artifacts[artifact] = stage.name

            stages.append(stage)
            seen_stage_names.add(stage.name)

        return stages

    def _parse_stage_definition(self, item: Any, index: int) -> StageDefinition:
        """Parse and validate a single stage definition."""
        if not isinstance(item, dict):
            raise ValueError(f"Stage entry #{index} must be a mapping")

        required_keys = {"name", "agent", "inputs", "outputs", "checks"}
        missing = sorted(required_keys - set(item))
        if missing:
            raise ValueError(f"Stage entry #{index} is missing required keys: {', '.join(missing)}")

        stage = StageDefinition(
            name=self._require_string(item["name"], f"stage[{index}].name"),
            agent=self._require_string(item["agent"], f"stage[{index}].agent"),
            inputs=self._require_string_list(item["inputs"], f"stage[{index}].inputs"),
            outputs=self._require_string_list(item["outputs"], f"stage[{index}].outputs"),
            checks=self._require_string_list(item["checks"], f"stage[{index}].checks"),
            depends_on=self._require_string_list(item.get("depends_on", []), f"stage[{index}].depends_on"),
            description=(
                self._require_string(item["description"], f"stage[{index}].description")
                if "description" in item and item["description"] is not None
                else None
            ),
        )

        if not stage.outputs:
            raise ValueError(f"Stage {stage.name} must define at least one output artifact")
        if not stage.checks:
            raise ValueError(f"Stage {stage.name} must define at least one validation check")

        return stage

    def _resolve_stage_dependencies(self, stages: List[StageDefinition], depends_on: List[str]) -> Set[str]:
        """Resolve the transitive dependency closure for a stage."""
        stage_by_name = {stage.name: stage for stage in stages}
        resolved: Set[str] = set()
        stack = list(depends_on)

        while stack:
            stage_name = stack.pop()
            if stage_name in resolved:
                continue
            resolved.add(stage_name)
            stack.extend(stage_by_name[stage_name].depends_on)

        return resolved

    def _require_string(self, value: Any, field_name: str) -> str:
        """Validate that a field is a string."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value.strip()

    def _require_string_list(self, value: Any, field_name: str) -> List[str]:
        """Validate that a field is a list of non-empty strings."""
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list")
        result: List[str] = []
        for index, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{field_name}[{index}] must be a non-empty string")
            result.append(item.strip())
        return result
