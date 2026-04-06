# Security

## Controls

| Control | Implemented | Enforced |
|--------|------------|----------|
| Secret scan with `security/scan-secrets.sh` | yes | yes |
| Python dependency audit with `security/audit-python.sh` | yes | yes |
| Pinned core Python dependencies in `backend/agentman/pyproject.toml` | yes | yes |
| Node dependency audit | NOT IMPLEMENTED | no |
| Container image scan | NOT IMPLEMENTED | no |

## Secret Management
- Method: symbolic secret declarations in `system/tri-engine/Agentfile` and generated template config files
- Storage: real secret values in repository source are NOT IMPLEMENTED; only secret names are tracked
- Validation: `bash security/scan-secrets.sh`

## Dependency Security
- Node: NOT IMPLEMENTED
- Python: `bash security/audit-python.sh` audits runtime dependencies declared in `backend/agentman/pyproject.toml`
- Containers: NOT IMPLEMENTED

## Known Vulnerabilities
- Core pinned Python dependencies: none found in the validated run on `2026-04-07`
- Generated framework runtime dependency combinations: NOT IMPLEMENTED audit coverage

## Threat Model

| Threat | Impact | Mitigation |
|--------|--------|-----------|
| Tracked credential or token enters the repository | credential exposure | `security/scan-secrets.sh` blocks common patterns |
| Vulnerable core Python dependency is introduced | compromised local/CI execution | `security/audit-python.sh` plus pinned versions in `backend/agentman/pyproject.toml` |
| `Agentfile` and `stages.yaml` diverge | invalid orchestration contract | parser cross-reference and stage-schema validation in `backend/agentman/src/agentman/agentfile_parser.py` |
| Dead or misleading runtime path is documented as active | operator executes invalid flow | docs are template-validated by `ci_cd/validate_docs.sh` |
| External MCP executable behaves unexpectedly | generated runtime failure | NOT IMPLEMENTED runtime validation in CI |

## Gaps
- Digest-pinned container base image: NOT IMPLEMENTED
- Audit of generated framework runtime requirements beyond the core package: NOT IMPLEMENTED
- Secret-format coverage beyond regex patterns: NOT IMPLEMENTED
- External MCP server execution gate: NOT IMPLEMENTED
