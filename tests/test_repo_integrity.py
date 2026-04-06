import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_agentfile_parser_module():
    module_path = ROOT / "backend" / "agentman" / "src" / "agentman" / "agentfile_parser.py"
    spec = importlib.util.spec_from_file_location("agentfile_parser", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normalized_layout_exists():
    required_paths = [
        ROOT / "frontend" / "open-antigravity",
        ROOT / "backend" / "agentman",
        ROOT / "docs" / "awesome-opencode",
        ROOT / "infra" / "codex-develop",
        ROOT / "system" / "tri-engine" / "Agentfile",
        ROOT / ".github" / "workflows" / "tri-engine-ci.yml",
        ROOT / "security" / "audit-node.sh",
        ROOT / "security" / "scan-secrets.sh",
        ROOT / "ci_cd" / "validate_workspace.sh",
    ]

    for path in required_paths:
        assert path.exists(), f"Missing required path: {path}"


def test_tri_engine_agentfile_parses():
    parser_module = load_agentfile_parser_module()
    config = parser_module.AgentfileParser().parse_file(str(ROOT / "system" / "tri-engine" / "Agentfile"))

    assert config.framework == "fast-agent"
    assert config.default_model == "anthropic/claude-3-sonnet-20241022"
    assert set(config.agents.keys()) == {"antigravity", "codex", "opencode"}
    assert "tri_engine_cicd" in config.orchestrators

    orchestrator = config.orchestrators["tri_engine_cicd"]
    assert orchestrator.default is True
    assert orchestrator.plan_iterations == 14
