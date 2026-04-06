# Setup

## Required Environment

| Tool | Version | Required | Notes |
|------|--------|----------|------|
| Python | `3.11+` | yes | CI uses `3.11`; local validation passed on `3.14.3` |
| `venv` | built-in | yes | used by `ci_cd/validate_workspace.sh` |
| `pip` | `26.0.1` during last validation | yes | upgraded by `ci_cd/validate_workspace.sh` |
| Bash | available in CI runner and local shell | yes | required by `ci_cd/*.sh` and `security/*.sh` |
| Node.js | NOT IMPLEMENTED | no | no remaining Node modules |
| Docker | NOT IMPLEMENTED | no | not required by current validator |

## Installation

```bash
python3 -m venv .venv-ci
source .venv-ci/bin/activate
python -m pip install --upgrade pip
python -m pip install -e 'backend/agentman[dev]'
```

## Validation

```bash
bash ci_cd/validate_docs.sh
bash ci_cd/validate_workspace.sh
```

## Module Execution

### backend/agentman

```bash
source .venv-ci/bin/activate
python -m agentman validate --build-check system/tri-engine
python -m agentman build system/tri-engine --output agent
python -m build backend/agentman
```

### system/tri-engine

```bash
source .venv-ci/bin/activate
python -m agentman validate system/tri-engine
```

### security

```bash
source .venv-ci/bin/activate
bash security/audit-python.sh
bash security/scan-secrets.sh
```

## Failure Modes

| Condition | Cause | Fix |
| --------- | ----- | --- |
| `python -m agentman validate system/tri-engine` fails | `Agentfile` and `stages.yaml` are inconsistent | align agent names, stage inputs, outputs, and dependencies |
| `pytest` fails | parser, builder, CLI, or integrity contract regression | fix the failing code or test fixture before rerunning |
| coverage is below `70%` | changed source without enough tests | add tests or remove dead paths |
| `bash security/audit-python.sh` fails | vulnerable core Python dependency | update pins in `backend/agentman/pyproject.toml` |
| `bash security/scan-secrets.sh` fails | secret-like content is tracked | remove or replace the tracked secret material |

## Non-Working Scenarios

* Deployment flow: NOT IMPLEMENTED
* HTTP API runtime: NOT IMPLEMENTED
* External MCP server startup validation: NOT IMPLEMENTED
* Docker runtime execution in CI: NOT IMPLEMENTED
