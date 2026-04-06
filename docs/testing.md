# Testing

## Test Types

| Type | Exists | Enforced |
|------|--------|----------|
| Unit and parser tests | yes | yes |
| Builder and CLI integration tests | yes | yes |
| Repo-integrity tests | yes | yes |
| Documentation structure validation | yes | yes |
| External runtime smoke tests | NOT IMPLEMENTED | no |
| HTTP/API tests | NOT IMPLEMENTED | no |

## Commands

```bash
source .venv-ci/bin/activate
bash ci_cd/validate_docs.sh
python -m pytest \
  --cov=backend/agentman/src/agentman \
  --cov-report=term-missing \
  --cov-fail-under=70 \
  backend/agentman/tests tests
```

## Coverage

* Current: `76.79%` in the validated run on `2026-04-07`
* Required: `70%`
* Enforcement: `--cov-fail-under=70` in `ci_cd/validate_workspace.sh`

## Gaps

* External MCP process startup tests: NOT IMPLEMENTED
* Docker runtime execution tests: NOT IMPLEMENTED
* Deployment tests: NOT IMPLEMENTED
* Network service tests: NOT IMPLEMENTED

## What Tests Prove

* `Agentfile` parsing and stage-schema validation work for the current tri-engine contract
* builder output contains required generated files including `orchestration.json`
* CLI `build`, `validate`, and `version` paths execute successfully
* repo-integrity assertions match the reduced repository layout

## What Tests Do NOT Prove

* external MCP server binaries start correctly
* generated `Dockerfile` images build or run
* any HTTP request/response behavior
* any deployment behavior
