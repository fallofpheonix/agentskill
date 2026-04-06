"""Role-constrained agent registry for the strict tri-engine runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Iterable, Optional


TaskHandler = Callable[..., dict]


class AgentRole(str, Enum):
    """Supported role assignments."""

    ORCHESTRATOR = "orchestrator"
    EXECUTOR = "executor"
    VALIDATOR = "validator"


class AgentCapability(str, Enum):
    """Supported capabilities."""

    PLAN = "plan"
    EXECUTE = "execute"
    VALIDATE = "validate"


@dataclass
class RegisteredAgent:
    """A registered runtime agent."""

    agent_id: str
    role: AgentRole
    handler: Optional[TaskHandler] = None
    capabilities: set[AgentCapability] = field(default_factory=set)


class AgentRegistry:
    """Register and resolve strict tri-engine agents."""

    def __init__(self) -> None:
        self._agents: Dict[str, RegisteredAgent] = {}

    def register(self, agent: RegisteredAgent) -> None:
        """Register a new agent after contract validation."""
        if agent.agent_id in self._agents:
            raise ValueError(f"Agent {agent.agent_id} is already registered")
        self._validate_agent_contract(agent)
        self._agents[agent.agent_id] = agent

    def get(self, agent_id: str) -> RegisteredAgent:
        """Return a previously registered agent."""
        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} is not registered")
        return self._agents[agent_id]

    def agents(self) -> Iterable[RegisteredAgent]:
        """Iterate over registered agents."""
        return self._agents.values()

    def _validate_agent_contract(self, agent: RegisteredAgent) -> None:
        """Reject role/capability overlap."""
        if agent.role == AgentRole.ORCHESTRATOR and agent.capabilities != {AgentCapability.PLAN}:
            raise ValueError(
                f"Orchestrator {agent.agent_id} capabilities must be exactly ['{AgentCapability.PLAN.value}']"
            )
        if agent.role == AgentRole.EXECUTOR and agent.capabilities != {AgentCapability.EXECUTE}:
            raise ValueError(
                f"Executor {agent.agent_id} capabilities must be exactly ['{AgentCapability.EXECUTE.value}']"
            )
        if agent.role == AgentRole.VALIDATOR and agent.capabilities != {AgentCapability.VALIDATE}:
            raise ValueError(
                f"Validator {agent.agent_id} capabilities must be exactly ['{AgentCapability.VALIDATE.value}']"
            )

    @classmethod
    def from_role_bindings(
        cls,
        role_bindings: Dict[str, str],
        handlers: Optional[Dict[str, TaskHandler]] = None,
    ) -> "AgentRegistry":
        """Create a registry from execution-plan role bindings."""
        handlers = handlers or {}
        registry = cls()
        registry.register(
            RegisteredAgent(
                agent_id=role_bindings["orchestrator"],
                role=AgentRole.ORCHESTRATOR,
                handler=handlers.get(role_bindings["orchestrator"]),
                capabilities={AgentCapability.PLAN},
            )
        )
        registry.register(
            RegisteredAgent(
                agent_id=role_bindings["executor"],
                role=AgentRole.EXECUTOR,
                handler=handlers.get(role_bindings["executor"]),
                capabilities={AgentCapability.EXECUTE},
            )
        )
        registry.register(
            RegisteredAgent(
                agent_id=role_bindings["validator"],
                role=AgentRole.VALIDATOR,
                handler=handlers.get(role_bindings["validator"]),
                capabilities={AgentCapability.VALIDATE},
            )
        )
        return registry
