"""Strict DAG execution engine for the tri-engine runtime."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional

try:  # pragma: no cover - exercised in generated bundles
    from agentman.agent_registry import AgentRegistry, AgentRole
    from agentman.schema_registry import SchemaRegistryError, validate_artifact_payload, validate_task_definition
except ImportError:  # pragma: no cover - exercised in generated bundles
    from agent_registry import AgentRegistry, AgentRole
    from schema_registry import SchemaRegistryError, validate_artifact_payload, validate_task_definition


class MessageType(str, Enum):
    """Protocol message types."""

    TASK_ASSIGNMENT = "task_assignment"
    TASK_RESULT = "task_result"
    VALIDATION_REQUEST = "validation_request"
    VALIDATION_RESULT = "validation_result"
    FAILURE_REPORT = "failure_report"
    STAGE_TRANSITION_REQUEST = "stage_transition_request"


class ExecutionError(RuntimeError):
    """Raised when execution cannot continue."""


@dataclass
class Message:
    """Strict message envelope."""

    sender_agent: str
    receiver_agent: str
    message_type: MessageType
    payload: Dict[str, Any]
    project_id: str
    execution_phase: str
    correlation_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the message envelope."""
        timestamp = datetime.now(timezone.utc).isoformat()
        checksum = hashlib.sha256(
            json.dumps(self.payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "message": {
                "message_id": str(uuid.uuid4()),
                "sender_agent": self.sender_agent,
                "receiver_agent": self.receiver_agent,
                "timestamp": timestamp,
                "message_type": self.message_type.value,
                "payload": self.payload,
                "context": {
                    "project_id": self.project_id,
                    "execution_phase": self.execution_phase,
                    "correlation_id": self.correlation_id,
                },
                "validation": {
                    "schema_version": "1.0",
                    "checksum": checksum,
                    "verified": True,
                },
            }
        }


def _default_rule_handlers() -> Dict[str, Callable[[Dict[str, Any]], tuple[bool, str]]]:
    """Return built-in validation rules."""
    return {
        "repo_inventory_components_classified": lambda payload: (
            bool(payload.get("components")),
            f"components={len(payload.get('components', []))}",
        ),
        "conflict_report_dependencies_resolved": lambda payload: (
            len(payload.get("unresolved_dependencies", [])) == 0,
            f"unresolved_dependencies={len(payload.get('unresolved_dependencies', []))}",
        ),
        "deletion_plan_structured": lambda payload: (
            bool(payload.get("deletions")) and bool(payload.get("rationale")),
            f"deletions={len(payload.get('deletions', []))}",
        ),
        "patched_codebase_has_modifications": lambda payload: (
            bool(payload.get("modifications")),
            f"modifications={len(payload.get('modifications', []))}",
        ),
        "enforced_contract_has_dag": lambda payload: (
            bool(payload.get("execution_dag")) and bool(payload.get("stage_transitions")),
            f"tasks={len(payload.get('execution_dag', {}).get('tasks', []))}",
        ),
        "validation_report_tests_pass": lambda payload: (
            payload.get("test_results", {}).get("failed", 1) == 0,
            f"failed={payload.get('test_results', {}).get('failed')}",
        ),
        "validation_report_build_success": lambda payload: (
            payload.get("build_status") == "success",
            f"build_status={payload.get('build_status')}",
        ),
        "validation_report_security_clean": lambda payload: (
            payload.get("security_status") == "clean",
            f"security_status={payload.get('security_status')}",
        ),
        "change_record_complete": lambda payload: (
            bool(payload.get("summary")) and bool(payload.get("details")),
            f"details={len(payload.get('details', []))}",
        ),
    }


class StrictExecutionEngine:
    """Execute a task DAG with strict role separation and validation gates."""

    def __init__(
        self,
        execution_plan: Dict[str, Any],
        registry: AgentRegistry,
        rule_handlers: Optional[Dict[str, Callable[[Dict[str, Any]], tuple[bool, str]]]] = None,
    ) -> None:
        self.execution_plan = execution_plan
        self.registry = registry
        self.rule_handlers = rule_handlers or _default_rule_handlers()
        self.message_log: List[Dict[str, Any]] = []
        self.agent_queues: Dict[str, Deque[Dict[str, Any]]] = {
            "orchestrator": deque(),
            "executor": deque(),
            "validator": deque(),
        }
        self.approved_artifacts: Dict[str, Dict[str, Any]] = {}
        self.pending_stage_artifacts: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.retry_counts: Dict[str, int] = defaultdict(int)
        self._seen_message_ids: set[str] = set()
        self._task_index = {
            task["task_id"]: task for task in self.execution_plan["execution_plan"]["tasks"]
        }
        self.validate_execution_plan(self.execution_plan)

    @staticmethod
    def validate_execution_plan(execution_plan: Dict[str, Any]) -> None:
        """Validate DAG structure and task contracts."""
        role_bindings = execution_plan.get("role_bindings")
        if not isinstance(role_bindings, dict):
            raise ExecutionError("role_bindings payload is missing")
        required_roles = {"orchestrator", "executor", "validator"}
        if set(role_bindings) != required_roles:
            raise ExecutionError("role_bindings must declare orchestrator, executor, and validator")

        plan = execution_plan.get("execution_plan")
        if not isinstance(plan, dict):
            raise ExecutionError("execution_plan payload is missing")

        tasks = plan.get("tasks", [])
        edges = plan.get("dag_edges", [])
        if not tasks:
            raise ExecutionError("execution_plan.tasks must be non-empty")

        seen = set()
        owners = {"executor", "validator"}
        stage_roles: Dict[str, set[str]] = defaultdict(set)
        stage_tasks: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        task_ids = set()

        for task in tasks:
            validate_task_definition(task)
            task_id = task["task_id"]
            if task_id in seen:
                raise ExecutionError(f"Duplicate task_id in execution plan: {task_id}")
            seen.add(task_id)
            task_ids.add(task_id)
            if task["owner_agent"] not in owners:
                raise ExecutionError(f"Unsupported task owner {task['owner_agent']} for {task_id}")
            stage_roles[task["stage_name"]].add(task["owner_agent"])
            stage_tasks[task["stage_name"]][task["owner_agent"]] = task

        for stage_name, present_roles in stage_roles.items():
            if present_roles != owners:
                raise ExecutionError(
                    f"Stage {stage_name} must contain exactly one executor task and one validator task"
                )
            validator_task = stage_tasks[stage_name]["validator"]
            executor_task = stage_tasks[stage_name]["executor"]
            if validator_task["depends_on_tasks"] != [executor_task["task_id"]]:
                raise ExecutionError(
                    f"Validator task {validator_task['task_id']} must depend only on {executor_task['task_id']}"
                )
            if not validator_task["validation"]["checks"]:
                raise ExecutionError(f"Validator task {validator_task['task_id']} must declare checks")

        adjacency: Dict[str, List[str]] = defaultdict(list)
        indegree: Dict[str, int] = {task_id: 0 for task_id in task_ids}
        for source, target in edges:
            if source not in task_ids or target not in task_ids:
                raise ExecutionError(f"DAG edge references undefined task: {source} -> {target}")
            adjacency[source].append(target)
            indegree[target] += 1

        queue = deque(sorted(task_id for task_id, degree in indegree.items() if degree == 0))
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for neighbor in adjacency[node]:
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    queue.append(neighbor)

        if visited != len(task_ids):
            raise ExecutionError("execution_plan contains a cycle")

    def execute(
        self,
        executor_handler: Callable[[Dict[str, Any], Dict[str, Dict[str, Any]], int], Dict[str, Dict[str, Any]]],
        initial_artifacts: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Execute the plan with a strict executor handler and built-in validation."""
        initial_artifacts = initial_artifacts or {}
        for artifact_key, payload in initial_artifacts.items():
            self.approved_artifacts[artifact_key] = payload

        for stage_name in self.execution_plan["execution_plan"]["stages"]:
            executor_task, validator_task = self._tasks_for_stage(stage_name)
            while True:
                if not self._run_executor_task(executor_task, executor_handler):
                    continue
                if self._run_validator_task(validator_task):
                    break
                self.retry_counts[executor_task["task_id"]] += 1
                if self.retry_counts[executor_task["task_id"]] > executor_task["execution"]["max_retries"]:
                    raise ExecutionError(
                        f"Validation failed for {validator_task['task_id']} and retries are exhausted"
                    )

        return {
            "approved_artifacts": self.approved_artifacts,
            "message_log": self.message_log,
            "retry_counts": {task_id: count for task_id, count in self.retry_counts.items() if count > 0},
        }

    def _tasks_for_stage(self, stage_name: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Return the executor and validator task for a stage."""
        executor_task = None
        validator_task = None
        for task in self.execution_plan["execution_plan"]["tasks"]:
            if task["stage_name"] != stage_name:
                continue
            if task["owner_agent"] == "executor":
                executor_task = task
            elif task["owner_agent"] == "validator":
                validator_task = task
        if executor_task is None or validator_task is None:
            raise ExecutionError(f"Stage {stage_name} is missing executor or validator task")
        return executor_task, validator_task

    def _queue_message(self, message: Message) -> Dict[str, Any]:
        """Queue and record a message."""
        envelope = message.to_dict()
        message_id = envelope["message"]["message_id"]
        if message_id in self._seen_message_ids:
            raise ExecutionError(f"Duplicate message_id detected: {message_id}")
        self._seen_message_ids.add(message_id)
        receiver_role = self._role_for_agent(envelope["message"]["receiver_agent"]).value
        self.agent_queues[receiver_role].append(envelope)
        self.message_log.append(envelope)
        return envelope

    def _role_for_agent(self, agent_id: str) -> AgentRole:
        """Resolve the registered role for an agent."""
        return self.registry.get(agent_id).role

    def _collect_inputs(self, task: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Collect approved inputs for a task."""
        inputs: Dict[str, Dict[str, Any]] = {}
        for artifact in task["input_artifacts"]:
            artifact_key = artifact["artifact_key"]
            if artifact["source"] == "external":
                if artifact_key not in self.approved_artifacts:
                    raise ExecutionError(f"Missing external artifact {artifact_key} for {task['task_id']}")
                validate_artifact_payload(artifact["schema_ref"], self.approved_artifacts[artifact_key])
                inputs[artifact_key] = self.approved_artifacts[artifact_key]
                continue

            if artifact_key not in self.approved_artifacts:
                raise ExecutionError(f"Missing approved artifact {artifact_key} for {task['task_id']}")
            inputs[artifact_key] = self.approved_artifacts[artifact_key]
        return inputs

    def _run_executor_task(
        self,
        task: Dict[str, Any],
        executor_handler: Callable[[Dict[str, Any], Dict[str, Dict[str, Any]], int], Dict[str, Dict[str, Any]]],
    ) -> bool:
        """Execute an executor-owned task and stage its outputs."""
        assigned_agent = task["assigned_agent"]
        if self._role_for_agent(assigned_agent) != AgentRole.EXECUTOR:
            raise ExecutionError(f"{assigned_agent} is not registered as executor")

        inputs = self._collect_inputs(task)
        correlation_id = str(uuid.uuid4())
        self._queue_message(
            Message(
                sender_agent=self.execution_plan["role_bindings"]["orchestrator"],
                receiver_agent=assigned_agent,
                message_type=MessageType.TASK_ASSIGNMENT,
                payload=task,
                project_id=self.execution_plan["execution_plan"]["project_id"],
                execution_phase="execution",
                correlation_id=correlation_id,
            )
        )

        started = time.monotonic()
        attempt = self.retry_counts[task["task_id"]]
        try:
            produced = executor_handler(task, inputs, attempt)
        except Exception as exc:
            return self._handle_execution_failure(task, f"execution_error:{exc}")
        duration = time.monotonic() - started
        if duration > task["execution"]["timeout_seconds"]:
            return self._handle_execution_failure(task, "execution_timeout")

        missing_outputs = {
            artifact["artifact_key"]
            for artifact in task["output_artifacts"]
            if artifact["artifact_key"] not in produced
        }
        if missing_outputs:
            raise ExecutionError(
                f"Task {task['task_id']} did not produce required outputs: {', '.join(sorted(missing_outputs))}"
            )

        staged_outputs: Dict[str, Dict[str, Any]] = {}
        for artifact in task["output_artifacts"]:
            artifact_key = artifact["artifact_key"]
            payload = produced[artifact_key]
            try:
                validate_artifact_payload(artifact["schema_ref"], payload)
            except SchemaRegistryError as exc:
                raise ExecutionError(str(exc)) from exc
            staged_outputs[artifact_key] = payload

        self.pending_stage_artifacts[task["stage_name"]] = staged_outputs
        self._queue_message(
            Message(
                sender_agent=assigned_agent,
                receiver_agent=self.execution_plan["role_bindings"]["orchestrator"],
                message_type=MessageType.TASK_RESULT,
                payload={
                    "task_id": task["task_id"],
                    "status": "completed",
                    "output_artifacts": sorted(staged_outputs.keys()),
                    "retry_count": attempt,
                },
                project_id=self.execution_plan["execution_plan"]["project_id"],
                execution_phase="execution",
                correlation_id=correlation_id,
            )
        )
        return True

    def _run_validator_task(self, task: Dict[str, Any]) -> bool:
        """Validate staged artifacts and open or block the stage gate."""
        assigned_agent = task["assigned_agent"]
        if self._role_for_agent(assigned_agent) != AgentRole.VALIDATOR:
            raise ExecutionError(f"{assigned_agent} is not registered as validator")

        staged_outputs = self.pending_stage_artifacts.get(task["stage_name"])
        if not staged_outputs:
            raise ExecutionError(f"Validator task {task['task_id']} has no staged outputs to validate")

        correlation_id = str(uuid.uuid4())
        self._queue_message(
            Message(
                sender_agent=self.execution_plan["role_bindings"]["orchestrator"],
                receiver_agent=assigned_agent,
                message_type=MessageType.VALIDATION_REQUEST,
                payload=task,
                project_id=self.execution_plan["execution_plan"]["project_id"],
                execution_phase="validation",
                correlation_id=correlation_id,
            )
        )

        results = []
        failures = []
        for check in task["validation"]["checks"]:
            artifact_key = check["artifact_key"]
            if artifact_key not in staged_outputs:
                failures.append(
                    {
                        "check_name": check["check_name"],
                        "evidence": f"artifact {artifact_key} not staged",
                    }
                )
                continue

            handler = self.rule_handlers.get(check["rule"])
            if handler is None:
                raise ExecutionError(f"Unknown validation rule {check['rule']} for {task['task_id']}")
            started = time.monotonic()
            passed, evidence = handler(staged_outputs[artifact_key])
            duration = time.monotonic() - started
            if duration > check["timeout_seconds"]:
                passed = False
                evidence = f"validation timeout after {duration:.3f}s"
            result = {
                "check_id": check["check_id"],
                "check_name": check["check_name"],
                "passed": passed,
                "evidence": evidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            results.append(result)
            if not passed:
                failures.append(result)

        if failures:
            self.pending_stage_artifacts.pop(task["stage_name"], None)
            self._queue_message(
                Message(
                    sender_agent=assigned_agent,
                    receiver_agent=self.execution_plan["role_bindings"]["orchestrator"],
                    message_type=MessageType.FAILURE_REPORT,
                    payload={
                        "task_id": task["task_id"],
                        "stage_name": task["stage_name"],
                        "failure_type": "validation_failure",
                        "check_failures": failures,
                    },
                    project_id=self.execution_plan["execution_plan"]["project_id"],
                    execution_phase="validation",
                    correlation_id=correlation_id,
                )
            )
            return False

        for artifact_key, payload in staged_outputs.items():
            self.approved_artifacts[artifact_key] = payload
        self._queue_message(
            Message(
                sender_agent=assigned_agent,
                receiver_agent=self.execution_plan["role_bindings"]["orchestrator"],
                message_type=MessageType.VALIDATION_RESULT,
                payload={
                    "task_id": task["task_id"],
                    "stage_name": task["stage_name"],
                    "overall_status": "approved",
                    "checks": results,
                },
                project_id=self.execution_plan["execution_plan"]["project_id"],
                execution_phase="validation",
                correlation_id=correlation_id,
            )
        )
        self._queue_message(
            Message(
                sender_agent=self.execution_plan["role_bindings"]["orchestrator"],
                receiver_agent=self.execution_plan["role_bindings"]["orchestrator"],
                message_type=MessageType.STAGE_TRANSITION_REQUEST,
                payload={
                    "from_stage": task["stage_name"],
                    "to_stage": self._next_stage(task["stage_name"]),
                    "gate_status": "open",
                },
                project_id=self.execution_plan["execution_plan"]["project_id"],
                execution_phase="finalization",
                correlation_id=correlation_id,
            )
        )
        return True

    def _next_stage(self, stage_name: str) -> Optional[str]:
        """Return the next stage name in declared order."""
        stages = self.execution_plan["execution_plan"]["stages"]
        index = stages.index(stage_name)
        if index + 1 >= len(stages):
            return None
        return stages[index + 1]

    def _handle_execution_failure(self, task: Dict[str, Any], failure_type: str) -> bool:
        """Apply retry limits for executor failures."""
        retries = self.retry_counts[task["task_id"]]
        self._queue_message(
            Message(
                sender_agent=task["assigned_agent"],
                receiver_agent=self.execution_plan["role_bindings"]["orchestrator"],
                message_type=MessageType.FAILURE_REPORT,
                payload={
                    "task_id": task["task_id"],
                    "stage_name": task["stage_name"],
                    "failure_type": failure_type,
                    "retry_count": retries,
                },
                project_id=self.execution_plan["execution_plan"]["project_id"],
                execution_phase="execution",
                correlation_id=str(uuid.uuid4()),
            )
        )
        if retries >= task["execution"]["max_retries"]:
            raise ExecutionError(f"Task {task['task_id']} failed permanently: {failure_type}")
        self.retry_counts[task["task_id"]] += 1
        return False
