#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv-ci
source .venv-ci/bin/activate

python -m pip install --upgrade pip
python -m pip install -e 'backend/agentman[dev]' build

npm ci --prefix docs/awesome-opencode
npm ci --prefix frontend/open-antigravity/mitmserver

npm run validate --prefix docs/awesome-opencode
npm run generate --prefix docs/awesome-opencode
npm run export --prefix docs/awesome-opencode
bash security/audit-node.sh

node --check frontend/open-antigravity/mitmserver/server.js
bash -n infra/codex-develop/*.sh

python -m pytest backend/agentman/tests tests
python -m build backend/agentman

bash security/scan-secrets.sh
