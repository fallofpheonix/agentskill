"""Agentman package for building MCP agents from Agentfiles."""

import sys

from agentman.common import perror
from agentman.version import print_version

assert sys.version_info >= (3, 10), "Python 3.10 or greater is required."

__all__ = ["perror", "init_cli", "print_version", "HelpException"]


def __getattr__(name):
    """Lazily expose CLI helpers without importing the full build stack on package import."""
    if name in {"HelpException", "init_cli"}:
        from agentman.cli import HelpException, init_cli

        exports = {
            "HelpException": HelpException,
            "init_cli": init_cli,
        }
        return exports[name]
    raise AttributeError(f"module 'agentman' has no attribute {name!r}")
