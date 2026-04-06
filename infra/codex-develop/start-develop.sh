#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

CODEX_REPOS="${CODEX_REPOS:-codex-feasibility-backend,codex-flare,codex-aktin-broker}"
load_repos

export FLARE_DEBUG="${FLARE_DEBUG:---debug}"
export CODEX_CONCEPT_TREE_PATH="${CODEX_CONCEPT_TREE_PATH:-$BASE_DIR/ontology/codex-code-tree.json}"
export CODEX_TERM_CODE_MAPPING_PATH="${CODEX_TERM_CODE_MAPPING_PATH:-$BASE_DIR/ontology/codex-term-code-mapping.json}"

prepare_ontology_artifacts

for repo_name in "${CODEX_REPOS_ARRAY[@]}"; do
  run_repo_compose "$repo_name" up -d
done
