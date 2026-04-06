#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TMP_REQUIREMENTS="$(mktemp)"
trap 'rm -f "$TMP_REQUIREMENTS"' EXIT

python - <<'PY' > "$TMP_REQUIREMENTS"
import tomllib
from pathlib import Path

pyproject = Path("backend/agentman/pyproject.toml")
data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
for dependency in data["project"]["dependencies"]:
    print(dependency)
PY

python -m pip_audit -r "$TMP_REQUIREMENTS"
