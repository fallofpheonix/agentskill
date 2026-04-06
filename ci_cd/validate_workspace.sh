#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv-ci
source .venv-ci/bin/activate

python -m pip install --upgrade pip
python -m pip install -e 'backend/agentman[dev]'

bash ci_cd/validate_docs.sh

python -m pytest \
  --cov=backend/agentman/src/agentman \
  --cov-report=term-missing \
  --cov-fail-under=70 \
  backend/agentman/tests tests

python -m agentman validate --build-check system/tri-engine
python -m build backend/agentman

bash security/audit-python.sh
bash security/scan-secrets.sh
