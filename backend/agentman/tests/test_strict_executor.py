"""Tests for the strict execution engine and role registry."""

from agentman.agent_registry import AgentRegistry, AgentRole, RegisteredAgent
from agentman.strict_executor import ExecutionError, StrictExecutionEngine


def make_execution_plan() -> dict:
    """Create a minimal strict execution plan for runtime tests."""
    return {
        "schema_version": "1.0",
        "role_bindings": {
            "orchestrator": "antigravity",
            "executor": "codex",
            "validator": "opencode",
        },
        "execution_plan": {
            "project_id": "test-project",
            "orchestrator": "tri_engine",
            "stages": ["analyze_repository"],
            "tasks": [
                {
                    "task_id": "T_00001_analyze_repository_exec",
                    "owner_agent": "executor",
                    "assigned_agent": "codex",
                    "stage_name": "analyze_repository",
                    "depends_on_tasks": [],
                    "input_artifacts": [
                        {
                            "artifact_key": "external:repository",
                            "schema_ref": "artifact_schema.json#/definitions/Repository",
                            "source": "external",
                            "required": True,
                        }
                    ],
                    "output_artifacts": [
                        {
                            "artifact_key": "repo_inventory",
                            "schema_ref": "artifact_schema.json#/definitions/RepoInventory",
                            "required": True,
                        }
                    ],
                    "execution": {
                        "instruction": "Build the repository inventory from the tracked tree only.",
                        "timeout_seconds": 3600,
                        "max_retries": 1,
                        "recovery_strategy": "retry",
                        "atomicity": "all_or_nothing",
                    },
                },
                {
                    "task_id": "T_00002_analyze_repository_val",
                    "owner_agent": "validator",
                    "assigned_agent": "opencode",
                    "stage_name": "analyze_repository",
                    "depends_on_tasks": ["T_00001_analyze_repository_exec"],
                    "input_artifacts": [
                        {
                            "artifact_key": "repo_inventory",
                            "schema_ref": "artifact_schema.json#/definitions/RepoInventory",
                            "source": "stage_output",
                            "required": True,
                        }
                    ],
                    "output_artifacts": [],
                    "validation": {
                        "checks": [
                            {
                                "check_id": "C_00001_classification_complete",
                                "check_name": "classification_complete",
                                "artifact_key": "repo_inventory",
                                "rule": "repo_inventory_components_classified",
                                "timeout_seconds": 300,
                                "failure_mode": "reject_task",
                            }
                        ],
                        "all_checks_required": True,
                    },
                },
            ],
            "dag_edges": [["T_00001_analyze_repository_exec", "T_00002_analyze_repository_val"]],
            "stage_transitions": [
                {
                    "from_stage": "analyze_repository",
                    "to_stage": None,
                    "gate_condition": "all_checks_passed AND validator_approval",
                    "rollback_on_failure": True,
                }
            ],
        },
    }


def make_initial_repository() -> dict:
    """Return a valid external repository artifact."""
    return {
        "root_path": "/repo",
        "tracked_files": ["README.md"],
        "timestamp": "2026-04-07T00:00:00Z",
    }


def test_registry_rejects_executor_with_validate_capability():
    """Executors cannot register validator capabilities."""
    registry = AgentRegistry()
    try:
        registry.register(
            RegisteredAgent(
                agent_id="bad-executor",
                role=AgentRole.EXECUTOR,
                capabilities=set(),
            )
        )
    except ValueError as exc:
        assert "Executor bad-executor capabilities" in str(exc)
    else:  # pragma: no cover - guard rail
        raise AssertionError("Expected executor capability validation to fail")


def test_execution_engine_rejects_cycles():
    """The execution plan must remain acyclic."""
    plan = make_execution_plan()
    plan["execution_plan"]["dag_edges"].append(
        ["T_00002_analyze_repository_val", "T_00001_analyze_repository_exec"]
    )

    try:
        StrictExecutionEngine.validate_execution_plan(plan)
    except ExecutionError as exc:
        assert "cycle" in str(exc)
    else:  # pragma: no cover - guard rail
        raise AssertionError("Expected cycle detection to fail")


def test_execution_engine_executes_and_approves_outputs():
    """A valid execution plan should approve staged artifacts."""
    plan = make_execution_plan()
    registry = AgentRegistry.from_role_bindings(plan["role_bindings"])
    engine = StrictExecutionEngine(plan, registry)

    def executor_handler(_task, _inputs, _attempt):
        return {
            "repo_inventory": {
                "components": [
                    {
                        "name": "README",
                        "type": "doc",
                        "role": "utility",
                        "path": "README.md",
                    }
                ],
                "dependencies": {},
                "timestamp": "2026-04-07T00:00:01Z",
            }
        }

    result = engine.execute(
        executor_handler,
        initial_artifacts={"external:repository": make_initial_repository()},
    )

    assert "repo_inventory" in result["approved_artifacts"]
    assert len(result["message_log"]) == 5
    assert result["retry_counts"] == {}


def test_execution_engine_retries_after_validation_failure():
    """Validation failures trigger a bounded retry and then approval."""
    plan = make_execution_plan()
    registry = AgentRegistry.from_role_bindings(plan["role_bindings"])
    engine = StrictExecutionEngine(
        plan,
        registry,
        rule_handlers={
            "repo_inventory_components_classified": lambda payload: (
                all(component["role"] != "deprecated" for component in payload["components"]),
                f"roles={[component['role'] for component in payload['components']]}",
            )
        },
    )

    def executor_handler(_task, _inputs, attempt):
        if attempt == 0:
            return {
                "repo_inventory": {
                    "components": [
                        {
                            "name": "README",
                            "type": "doc",
                            "role": "deprecated",
                            "path": "README.md",
                        }
                    ],
                    "dependencies": {},
                    "timestamp": "2026-04-07T00:00:01Z",
                }
            }
        return {
            "repo_inventory": {
                "components": [
                    {
                        "name": "README",
                        "type": "doc",
                        "role": "utility",
                        "path": "README.md",
                    }
                ],
                "dependencies": {},
                "timestamp": "2026-04-07T00:00:02Z",
            }
        }

    result = engine.execute(
        executor_handler,
        initial_artifacts={"external:repository": make_initial_repository()},
    )

    assert result["retry_counts"]["T_00001_analyze_repository_exec"] == 1
    assert result["approved_artifacts"]["repo_inventory"]["components"][0]["name"] == "README"
