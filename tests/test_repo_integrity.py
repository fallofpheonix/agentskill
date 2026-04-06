import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_agentfile_parser_module():
    src_path = ROOT / "backend" / "agentman" / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    module_path = ROOT / "backend" / "agentman" / "src" / "agentman" / "agentfile_parser.py"
    spec = importlib.util.spec_from_file_location("agentfile_parser", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_minimal_layout_exists():
    required_paths = [
        ROOT / "backend" / "agentman",
        ROOT / "backend" / "agentman" / "src" / "agentman" / "strict_executor.py",
        ROOT / "backend" / "agentman" / "src" / "agentman" / "agent_registry.py",
        ROOT / "backend" / "agentman" / "src" / "agentman" / "schemas" / "task_schema.json",
        ROOT / "backend" / "agentman" / "src" / "agentman" / "schemas" / "artifact_schema.json",
        ROOT / "system" / "tri-engine" / "Agentfile",
        ROOT / "system" / "tri-engine" / "stages.yaml",
        ROOT / ".github" / "workflows" / "tri-engine-ci.yml",
        ROOT / "security" / "audit-python.sh",
        ROOT / "security" / "scan-secrets.sh",
        ROOT / "ci_cd" / "validate_workspace.sh",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "setup.md",
        ROOT / "docs" / "ci_cd.md",
        ROOT / "docs" / "security.md",
        ROOT / "docs" / "testing.md",
    ]

    for path in required_paths:
        assert path.exists(), f"Missing required path: {path}"


def test_removed_surface_stays_removed():
    removed_paths = [
        ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md",
        ROOT / "backend" / "agentman" / "src" / "agentman" / "frameworks" / "agno.py",
        ROOT / "docs" / "awesome-opencode",
        ROOT / "frontend",
        ROOT / "infra",
    ]

    for path in removed_paths:
        assert not path.exists(), f"Removed path reintroduced: {path}"


def test_tri_engine_agentfile_parses_with_stage_schema():
    parser_module = load_agentfile_parser_module()
    config = parser_module.AgentfileParser().parse_file(str(ROOT / "system" / "tri-engine" / "Agentfile"))

    assert config.framework == "fast-agent"
    assert config.base_image == "python:3.11-slim"
    assert config.default_model == "anthropic/claude-3-sonnet-20241022"
    assert set(config.agents.keys()) == {"antigravity", "codex", "opencode"}
    assert "tri_engine_cicd" in config.orchestrators

    orchestrator = config.orchestrators["tri_engine_cicd"]
    assert orchestrator.default is True
    assert orchestrator.plan_iterations == 8
    assert orchestrator.stage_schema == "stages.yaml"
    assert orchestrator.role_bindings.orchestrator == "antigravity"
    assert orchestrator.role_bindings.executor == "codex"
    assert orchestrator.role_bindings.validator == "opencode"
    assert [stage.name for stage in orchestrator.stages] == [
        "analyze_repository",
        "repair_core",
        "validate_system",
        "finalize_output",
    ]
    assert orchestrator.stages[1].depends_on == ["analyze_repository"]
    assert orchestrator.stages[2].executor_task.input_artifacts[0].artifact_key == "patched_codebase"
    assert orchestrator.stages[2].validator_task.validation.checks[0].check_name == "tests_pass"
