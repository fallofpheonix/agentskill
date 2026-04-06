#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

load_repos

for repo_name in "${CODEX_REPOS_ARRAY[@]}"; do
  run_repo_compose "$repo_name" down
done
