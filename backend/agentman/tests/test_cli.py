"""CLI tests for the minimal Agentman command surface."""

import runpy
from pathlib import Path

import pytest

from agentman import cli


def write_minimal_tri_engine_files(base_dir: Path) -> None:
    """Create a minimal Agentfile and stage schema for CLI tests."""
    (base_dir / "stages.yaml").write_text(
        """
version: 1
stages:
  - name: analyze
    agent: antigravity
    inputs: [external:repository]
    outputs: [repo_inventory]
    checks: [classification_complete]
  - name: validate
    agent: opencode
    depends_on: [analyze]
    inputs: [repo_inventory]
    outputs: [validation_report]
    checks: [tests_pass]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (base_dir / "Agentfile").write_text(
        """
FROM python:3.11-slim
FRAMEWORK fast-agent
MODEL anthropic/claude-3-sonnet-20241022
AGENT antigravity
INSTRUCTION Analyze
AGENT opencode
INSTRUCTION Validate
ORCHESTRATOR tri_engine
AGENTS antigravity opencode
STAGE_SCHEMA stages.yaml
DEFAULT 1
CMD ["python", "agent.py"]
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_resolve_context_path_rejects_missing_directory():
    """resolve_context_path should reject missing paths."""
    with pytest.raises(ValueError, match="Build context path not found"):
        cli.resolve_context_path("/tmp/agentman-does-not-exist")


def test_build_command_generates_output(tmp_path, monkeypatch):
    """The build command should create a deterministic output bundle."""
    write_minimal_tri_engine_files(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["agentman", "build", "--output", "out", str(tmp_path)],
    )

    cli.main()

    output_dir = tmp_path / "out"
    assert (output_dir / "agent.py").exists()
    assert (output_dir / "orchestration.json").exists()
    assert (output_dir / "stages.yaml").exists()


def test_validate_command_runs_build_check(tmp_path, monkeypatch, capsys):
    """The validate command should parse the schema and perform a throwaway build."""
    write_minimal_tri_engine_files(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["agentman", "validate", "--build-check", str(tmp_path)],
    )

    cli.main()

    output = capsys.readouterr().out
    assert "Valid Agentfile" in output
    assert "stages: 2" in output


def test_version_command_quiet(monkeypatch, capsys):
    """The quiet version command should print only the version string."""
    monkeypatch.setattr("sys.argv", ["agentman", "--quiet", "version"])

    cli.main()

    assert capsys.readouterr().out.strip() == "0.1.6"


def test_main_entrypoint_invokes_cli_main(monkeypatch):
    """The package entrypoint should dispatch to agentman.cli.main."""
    called = {"value": False}

    def fake_main():
        called["value"] = True

    monkeypatch.setattr("agentman.cli.main", fake_main)
    runpy.run_module("agentman.__main__", run_name="__main__")

    assert called["value"] is True
