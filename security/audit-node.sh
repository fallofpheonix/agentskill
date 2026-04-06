#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT"

npm audit --omit=dev --audit-level=moderate --prefix docs/awesome-opencode
npm audit --omit=dev --audit-level=moderate --prefix frontend/open-antigravity/mitmserver
