"""Agentman package for building MCP agents from Agentfiles."""

import sys

from agentman.version import version

assert sys.version_info >= (3, 10), "Python 3.10 or greater is required."

__all__ = ["version"]
