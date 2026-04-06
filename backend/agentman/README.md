# agentman

## System Classification
- Type: toolchain
- Deployable: no
- Runtime Surface: `python -m agentman`, `python -m build backend/agentman`

## Source of Truth
- architecture: ../../docs/architecture.md
- setup: ../../docs/setup.md
- ci_cd: ../../docs/ci_cd.md
- security: ../../docs/security.md
- testing: ../../docs/testing.md

## Modules

| Path | Role | Entry Points | Validated In CI |
|------|------|-------------|-----------------|
| `backend/agentman/src/agentman` | Parser, validator, and generator implementation | `backend/agentman/src/agentman/__main__.py`, `backend/agentman/src/agentman/cli.py` | yes |
| `backend/agentman/src/agentman/frameworks` | Fast-agent-specific file emitter | `backend/agentman/src/agentman/frameworks/fast_agent.py` | yes |
| `backend/agentman/tests` | Parser, builder, CLI, and framework generation tests | `backend/agentman/tests` | yes |
| `backend/agentman/pyproject.toml` | Package metadata and dependency pins | `backend/agentman/pyproject.toml` | yes |

## Execution Guarantees
- Build: `python -m build backend/agentman` succeeds and packages the current CLI, parser, builder, and tests
- Test: `python -m pytest --cov=backend/agentman/src/agentman --cov-fail-under=70 backend/agentman/tests tests` passes
- Security: pinned core dependencies in `backend/agentman/pyproject.toml` pass `bash security/audit-python.sh`
- CI/CD: root workflow executes `bash ci_cd/validate_workspace.sh`, which includes package validation for `backend/agentman`

## Non-Goals
- HTTP API: NOT IMPLEMENTED
- Long-running backend service: NOT IMPLEMENTED
- Runtime container execution: NOT IMPLEMENTED
- External MCP process startup validation: NOT IMPLEMENTED

## Known Limitations
- Generated framework runtime requirements beyond the core package are not audited unless explicitly installed
- `fast-agent` and MCP executables are emitted into generated output, not validated as running processes in CI
- The package generates bundles; it does not execute deployed agents

## Quick Start (Verified Only)

```bash
python3 -m venv .venv-ci
source .venv-ci/bin/activate
python -m pip install --upgrade pip
python -m pip install -e 'backend/agentman[dev]'
python -m agentman validate --build-check system/tri-engine
python -m build backend/agentman
```

## Failure Conditions

* `python -m agentman validate --build-check system/tri-engine` fails
* `python -m build backend/agentman` fails
* package coverage drops below `70%`
* `bash security/audit-python.sh` reports a known vulnerability in pinned core dependencies
