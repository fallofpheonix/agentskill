"""Test script to verify EXPOSE and CMD instructions are properly handled in Dockerfile generation."""

import tempfile
from pathlib import Path

from agentman.agentfile_parser import AgentfileParser
from agentman.agent_builder import AgentBuilder


def test_dockerfile_generation_with_expose_and_cmd():
    """Test that EXPOSE and CMD instructions from Agentfile are included in generated Dockerfile."""

    # Create a test Agentfile content with EXPOSE and CMD instructions
    agentfile_content = """
FROM python:3.11-slim
MODEL anthropic/claude-3-sonnet-20241022
RUN apt-get update && apt-get install -y wget
EXPOSE 8080
EXPOSE 9090
CMD ["python", "agent.py"]
"""

    # Parse the Agentfile
    parser = AgentfileParser()
    config = parser.parse_content(agentfile_content)

    # Create a temporary directory for output
    with tempfile.TemporaryDirectory() as temp_dir:
        # Build the agent
        builder = AgentBuilder(config, temp_dir)
        builder._generate_dockerfile()

        # Read the generated Dockerfile
        dockerfile_path = Path(temp_dir) / "Dockerfile"
        with open(dockerfile_path, 'r') as f:
            dockerfile_content = f.read()

        # Verify EXPOSE and CMD instructions are present
        assert "EXPOSE 8080" in dockerfile_content, "EXPOSE 8080 not found in Dockerfile"
        assert "EXPOSE 9090" in dockerfile_content, "EXPOSE 9090 not found in Dockerfile"
        assert 'CMD ["python", "agent.py"]' in dockerfile_content, "CMD instruction not found in Dockerfile"
        assert "RUN apt-get update && apt-get install -y wget" in dockerfile_content, "Custom RUN instruction not found"
