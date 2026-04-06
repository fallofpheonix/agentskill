#!/usr/bin/env bash

set -euo pipefail

export COMPOSE_PROJECT="${COMPOSE_PROJECT:-codex-develop}"
DEFAULT_CODEX_REPOS="codex-keycloak,codex-feasibility-gui,codex-feasibility-backend,codex-flare"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

load_repos() {
  local csv="${CODEX_REPOS:-$DEFAULT_CODEX_REPOS}"
  csv="${csv//, /,}"
  IFS=',' read -r -a CODEX_REPOS_ARRAY <<< "$csv"
}

compose_project() {
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose -p "$COMPOSE_PROJECT" "$@"
    return
  fi

  if docker compose version >/dev/null 2>&1; then
    docker compose -p "$COMPOSE_PROJECT" "$@"
    return
  fi

  echo "Docker Compose is not available." >&2
  return 1
}

run_repo_compose() {
  local repo_name="$1"
  shift

  local repo_dir="$BASE_DIR/$repo_name"
  if [[ ! -d "$repo_dir" ]]; then
    echo "Skipping missing repository: $repo_name" >&2
    return 0
  fi

  (
    cd "$repo_dir"
    case "$repo_name" in
      codex-processes-ap2)
        echo "No compose target defined for $repo_name"
        ;;
      codex-aktin-broker)
        cd aktin-broker
        compose_project "$@"
        sleep 10
        cd ../aktin-client
        compose_project "$@"
        ;;
      num-knoten)
        cd fhir-server/blaze-server
        compose_project "$@"
        ;;
      *)
        compose_project "$@"
        ;;
    esac
  )
}

prepare_ontology_artifacts() {
  local profiles_dir="$BASE_DIR/codex-gecco-to-ui-profiles"
  local ontology_dir="$BASE_DIR/ontology"

  if [[ ! -d "$profiles_dir" ]]; then
    echo "Skipping ontology sync because $profiles_dir is missing." >&2
    return 0
  fi

  mkdir -p "$ontology_dir"

  if [[ -d "$profiles_dir/ui-profiles" ]]; then
    rm -rf "$ontology_dir/ui-profiles"
    cp -R "$profiles_dir/ui-profiles" "$ontology_dir"
  fi

  if [[ -f "$profiles_dir/mapping/TermCodeMapping.json" ]]; then
    cp "$profiles_dir/mapping/TermCodeMapping.json" "$ontology_dir/codex-term-code-mapping.json"
  fi

  if [[ -f "$profiles_dir/mapping/TermCodeTree.json" ]]; then
    cp "$profiles_dir/mapping/TermCodeTree.json" "$ontology_dir/codex-code-tree.json"
  fi
}
