"""JSON schema registry and validation helpers for the strict tri-engine runtime."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft7Validator


SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
TASK_SCHEMA_PATH = SCHEMA_DIR / "task_schema.json"
ARTIFACT_SCHEMA_PATH = SCHEMA_DIR / "artifact_schema.json"


class SchemaRegistryError(ValueError):
    """Raised when schema references or payloads are invalid."""


def _load_json_file(path: Path) -> Dict[str, Any]:
    """Load a JSON document from disk."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_task_schema() -> Dict[str, Any]:
    """Load the task schema document."""
    return _load_json_file(TASK_SCHEMA_PATH)


@lru_cache(maxsize=1)
def load_artifact_schema() -> Dict[str, Any]:
    """Load the artifact schema document."""
    return _load_json_file(ARTIFACT_SCHEMA_PATH)


def artifact_definition_names() -> Dict[str, Any]:
    """Return all named artifact definitions."""
    return load_artifact_schema().get("definitions", {})


def resolve_artifact_schema_ref(schema_ref: str) -> Dict[str, Any]:
    """Resolve a local artifact schema reference."""
    prefix = "artifact_schema.json#/definitions/"
    if not schema_ref.startswith(prefix):
        raise SchemaRegistryError(
            f"Unsupported artifact schema ref: {schema_ref}. Expected prefix {prefix}"
        )

    definition_name = schema_ref[len(prefix):]
    definitions = artifact_definition_names()
    if definition_name not in definitions:
        raise SchemaRegistryError(
            f"Unknown artifact schema definition {definition_name} for ref {schema_ref}"
        )

    schema = dict(definitions[definition_name])
    schema["$schema"] = load_artifact_schema().get("$schema", "http://json-schema.org/draft-07/schema#")
    return schema


def validate_artifact_schema_ref(schema_ref: str) -> None:
    """Validate that an artifact schema reference exists."""
    resolve_artifact_schema_ref(schema_ref)


def validate_task_definition(task: Dict[str, Any]) -> None:
    """Validate a task definition against the task schema."""
    validator = Draft7Validator(load_task_schema())
    errors = sorted(validator.iter_errors(task), key=lambda item: list(item.path))
    if errors:
        message = "; ".join(error.message for error in errors)
        raise SchemaRegistryError(f"Invalid task definition {task.get('task_id', '<unknown>')}: {message}")


def validate_artifact_payload(schema_ref: str, payload: Dict[str, Any]) -> None:
    """Validate an artifact payload against its referenced schema."""
    validator = Draft7Validator(resolve_artifact_schema_ref(schema_ref))
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        message = "; ".join(error.message for error in errors)
        raise SchemaRegistryError(f"Artifact payload failed validation for {schema_ref}: {message}")
