"""Base framework interface for AgentMan."""

from abc import ABC, abstractmethod
from typing import List
from pathlib import Path

from agentman.agentfile_parser import AgentfileConfig


class BaseFramework(ABC):
    """Base class for framework implementations."""

    def __init__(self, config: AgentfileConfig, output_dir: Path, source_dir: Path):
        self.config = config
        self.output_dir = output_dir
        self.source_dir = source_dir
        self.has_prompt_file = (source_dir / "prompt.txt").exists()

    @abstractmethod
    def build_agent_content(self) -> str:
        """Build the main agent file content."""
        pass

    @abstractmethod
    def get_requirements(self) -> List[str]:
        """Get framework-specific requirements."""
        pass

    @abstractmethod
    def generate_config_files(self) -> None:
        """Generate framework-specific configuration files."""
        pass

    @abstractmethod
    def get_dockerfile_config_lines(self) -> List[str]:
        """Get framework-specific Dockerfile configuration lines."""
        pass

    def _ensure_output_dir(self):
        """Ensure output directory exists."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
