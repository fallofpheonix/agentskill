# CI/CD

## Pipeline Overview

```text
docs -> test -> build -> security
```

## Jobs

### Build

* Inputs: repository checkout, Python `3.11`, `backend/agentman[dev]`
* Outputs: throwaway generated bundle from `system/tri-engine`, Python package artifacts from `backend/agentman`
* Validation: logical phase inside the single GitHub Actions `validate` job; executes `python -m agentman validate --build-check system/tri-engine`, `python -m build backend/agentman`

### Test

* Coverage threshold: `70%`
* Test types: logical phase inside the single GitHub Actions `validate` job; unit, parser/builder integration, CLI, repo integrity

### Security

* Tools: `pip-audit`, `rg`
* Enforcement: logical phase inside the single GitHub Actions `validate` job; executes `bash security/audit-python.sh`, `bash security/scan-secrets.sh`

### Deploy

* Target: NOT IMPLEMENTED
* Trigger: NOT IMPLEMENTED
* Rollback: NOT IMPLEMENTED

## Failure Gates

| Stage | Condition | Blocking |
| ----- | --------- | -------- |
| build | `python -m agentman validate --build-check system/tri-engine` fails | yes |
| build | `python -m build backend/agentman` fails | yes |
| test | `pytest` fails | yes |
| test | coverage `< 70%` | yes |
| security | `bash security/audit-python.sh` fails | yes |
| security | `bash security/scan-secrets.sh` fails | yes |
| deploy | deploy requested by docs or workflow | yes |

## Local Reproduction

```bash
bash ci_cd/validate_workspace.sh
```

## Missing Capabilities

* Deploy stage implementation: NOT IMPLEMENTED
* Rollback logic: NOT IMPLEMENTED
* Docker image build/run validation: NOT IMPLEMENTED
* External MCP runtime validation: NOT IMPLEMENTED
