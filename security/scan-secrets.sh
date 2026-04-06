#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PATTERN='ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|GOCSPX-[A-Za-z0-9_-]{10,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY'

if rg -n "$PATTERN" . \
  --glob '!**/package-lock.json' \
  --glob '!**/uv.lock' \
  --glob '!**/__pycache__/**'
then
  echo "Secret scan failed." >&2
  exit 1
fi

echo "Secret scan passed."
