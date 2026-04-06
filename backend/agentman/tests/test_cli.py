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
INSTRUCTION Plan
AGENT codex
INSTRUCTION Execute
AGENT opencode
INSTRUCTION Validate
ORCHESTRATOR tri_engine
AGENTS antigravity codex opencode
STAGE_SCHEMA stages.yaml
DEFAULT 1
CMD ["python", "agent.py"]
""".strip()
        + "\n",
        encoding="utf-8",
    )


def write_execution_artifacts(base_dir: Path) -> Path:
    """Create deterministic artifact payloads for CLI execution tests."""
    artifact_dir = base_dir / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "external__repository.json").write_text(
        """
{"root_path": "/repo", "tracked_files": ["README.md"], "timestamp": "2026-04-07T00:00:00Z"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "repo_inventory.json").write_text(
        """
{"components": [{"name": "README", "type": "doc", "role": "utility", "path": "README.md"}], "dependencies": {}, "timestamp": "2026-04-07T00:00:01Z"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "validation_report.json").write_text(
        """
{"test_results": {"passed": 1, "failed": 0, "skipped": 0}, "build_status": "success", "security_status": "clean", "timestamp": "2026-04-07T00:00:02Z"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return artifact_dir


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
    assert (output_dir / "execution_dag.json").exists()
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


def test_execute_command_runs_strict_dag(tmp_path, monkeypatch, capsys):
    """The execute command should run the strict DAG with deterministic JSON payloads."""
    write_minimal_tri_engine_files(tmp_path)
    artifact_dir = write_execution_artifacts(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["agentman", "execute", "--artifacts", str(artifact_dir), str(tmp_path)],
    )

    cli.main()

    output = capsys.readouterr().out
    assert "Executed strict DAG" in output
    assert "approved artifacts" in output


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
