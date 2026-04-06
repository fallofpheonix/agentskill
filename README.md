# agentskill

## System Classification
- Type: toolchain
- Deployable: no
- Runtime Surface: `python -m agentman`, `bash ci_cd/validate_workspace.sh`, `bash ci_cd/validate_docs.sh`, `bash security/audit-python.sh`, `bash security/scan-secrets.sh`

## Source of Truth
- architecture: docs/architecture.md
- setup: docs/setup.md
- ci_cd: docs/ci_cd.md
- security: docs/security.md
- testing: docs/testing.md

## Modules

| Path | Role | Entry Points | Validated In CI |
|------|------|-------------|-----------------|
| `backend/agentman` | Deterministic `Agentfile` parser, validator, and generator | `backend/agentman/src/agentman/__main__.py`, `backend/agentman/src/agentman/cli.py` | yes |
| `system/tri-engine` | Tri-engine contract and enforced stage schema | `system/tri-engine/Agentfile`, `system/tri-engine/stages.yaml`, `system/tri-engine/prompt.txt` | yes |
| `ci_cd` | Local validation entrypoints | `ci_cd/validate_workspace.sh`, `ci_cd/validate_docs.sh` | yes |
| `security` | Security gate scripts | `security/audit-python.sh`, `security/scan-secrets.sh` | yes |
| `docs` | Repository documentation set | `README.md`, `docs/architecture.md`, `docs/setup.md`, `docs/ci_cd.md`, `docs/security.md`, `docs/testing.md` | yes |
| `tests` | Pytest suite and repo-integrity assertions | `backend/agentman/tests`, `tests/test_repo_integrity.py` | yes |

## Execution Guarantees
- Build: `python -m agentman build system/tri-engine --output agent` generates a deterministic bundle including `orchestration.json` and copied `stages.yaml`
- Test: `pytest` passes at `>=70%` coverage for `backend/agentman/src/agentman`
- Security: core Python dependencies from `backend/agentman/pyproject.toml` pass `pip-audit`; tracked files pass `security/scan-secrets.sh`
- CI/CD: GitHub Actions runs `bash ci_cd/validate_workspace.sh` on `pull_request` and `push` to `main`; deploy is `NOT IMPLEMENTED`

## Non-Goals
- HTTP API: NOT IMPLEMENTED
- Frontend application: NOT IMPLEMENTED
- Deployment target: NOT IMPLEMENTED
- Docker runtime execution in CI: NOT IMPLEMENTED
- External MCP server execution in CI: NOT IMPLEMENTED

## Known Limitations
- Generated framework runtime dependencies beyond the core package are not audited unless explicitly installed
- `system/tri-engine/Agentfile` pins `python:3.11-slim` by tag, not digest
- Secret scanning is regex-based
- `backend/agentman` is a CLI and generator, not a long-running service

## Quick Start (Verified Only)

```bash
python3 -m venv .venv-ci
source .venv-ci/bin/activate
python -m pip install --upgrade pip
python -m pip install -e 'backend/agentman[dev]'
bash ci_cd/validate_workspace.sh
```

## Failure Conditions

* `bash ci_cd/validate_workspace.sh` fails
* `system/tri-engine/Agentfile` and `system/tri-engine/stages.yaml` diverge
* coverage drops below `70%`
* `pip-audit` finds a known vulnerability in the core pinned dependencies
* `security/scan-secrets.sh` detects a matching secret pattern
