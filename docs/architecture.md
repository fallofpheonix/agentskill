# Architecture

## System Topology
```text
system/tri-engine/Agentfile
        |
        +--> backend/agentman/src/agentman/agentfile_parser.py
        |        |
        |        `--> loads system/tri-engine/stages.yaml
        |             validates:
        |             - agent references
        |             - stage ordering
        |             - artifact producers and consumers
        |
        `--> backend/agentman/src/agentman/agent_builder.py
                 |
                 `--> generated output bundle
                     - agent.py
                     - fastagent.config.yaml
                     - fastagent.secrets.yaml
                     - orchestration.json
                     - Dockerfile
                     - requirements.txt
                     - .dockerignore
                     - prompt.txt when present
                     - copied stage schema file

ci_cd/validate_workspace.sh
        |
        +--> ci_cd/validate_docs.sh
        +--> pytest with coverage gate
        +--> python -m agentman validate --build-check system/tri-engine
        +--> python -m build backend/agentman
        +--> security/audit-python.sh
        `--> security/scan-secrets.sh
```

## Modules

### backend/agentman
- Purpose: Parse `Agentfile`, validate stage schemas, and generate deterministic runtime bundles
- Inputs: `Agentfile`, optional `prompt.txt`, optional `stages.yaml`
- Outputs: `agent.py`, framework config files, `orchestration.json`, `Dockerfile`, `requirements.txt`, `.dockerignore`
- Dependencies: Python `3.11+`, `PyYAML==6.0.2`
- Runtime: yes

### system/tri-engine
- Purpose: Declare the tri-engine agent set and the enforced stage contract
- Inputs: repository working tree
- Outputs: parsed `AgentfileConfig`, loaded `StageDefinition` objects, copied schema in generated output
- Dependencies: `backend/agentman/src/agentman/agentfile_parser.py`
- Runtime: yes

### ci_cd
- Purpose: Validate documentation, tests, build, and security gates
- Inputs: repository working tree, Python environment
- Outputs: pass/fail validation result
- Dependencies: Bash, Python, `backend/agentman[dev]`
- Runtime: yes

### security
- Purpose: Audit pinned Python dependencies and scan tracked files for secret patterns
- Inputs: `backend/agentman/pyproject.toml`, repository files
- Outputs: pass/fail audit result
- Dependencies: `pip-audit`, `rg`
- Runtime: yes

### docs
- Purpose: Define the repository contract in a fixed template
- Inputs: repository state
- Outputs: Markdown files
- Dependencies: `ci_cd/validate_docs.sh`
- Runtime: no

### tests
- Purpose: Verify parser, builder, CLI, framework generation, and repo integrity
- Inputs: source tree
- Outputs: pytest pass/fail result and coverage report
- Dependencies: `pytest`, `pytest-cov`
- Runtime: no

## Orchestration Model

### Agents
| Agent | Responsibility | Enforced | Notes |
|-------|---------------|----------|------|
| `antigravity` | classification, stage ordering, final output discipline | yes | declared in `system/tri-engine/Agentfile` and referenced by `stages.yaml` |
| `codex` | code and config modifications after required inputs exist | yes | declared in `system/tri-engine/Agentfile` and referenced by `stages.yaml` |
| `opencode` | validation and rejection of invalid output | yes | declared in `system/tri-engine/Agentfile` and referenced by `stages.yaml` |

### Stages (ENFORCED)

| Stage | Input | Output | Validator |
|-------|------|--------|----------|
| `analyze_repository` | `external:repository` | `repo_inventory`, `conflict_report`, `deletion_plan` | `classification_complete`, `dependency_paths_resolved` |
| `repair_core` | `repo_inventory`, `conflict_report`, `deletion_plan` | `patched_codebase`, `enforced_contract` | `no_dead_paths`, `imports_resolved`, `runtime_surface_minimized` |
| `validate_system` | `patched_codebase`, `enforced_contract` | `validation_report` | `tests_pass`, `build_pass`, `security_pass` |
| `finalize_output` | `validation_report` | `change_record` | `output_format_enforced` |

## Data Contracts

### AgentfileConfig
- Producer: `backend/agentman/src/agentman/agentfile_parser.py`
- Consumer: `backend/agentman/src/agentman/agent_builder.py`, `backend/agentman/src/agentman/cli.py`
- Schema: Python dataclass `AgentfileConfig`
- Validation: parser line validation plus cross-reference validation

### Stage Schema
- Producer: `system/tri-engine/stages.yaml`
- Consumer: `backend/agentman/src/agentman/agentfile_parser.py`
- Schema: YAML mapping with `stages` list; each stage requires `name`, `agent`, `inputs`, `outputs`, `checks`
- Validation: `_load_stage_schema()` in `backend/agentman/src/agentman/agentfile_parser.py`

### Build Manifest
- Producer: `backend/agentman/src/agentman/agent_builder.py`
- Consumer: generated output bundle consumers
- Schema: `orchestration.json`
- Validation: `_validate_output()` in `backend/agentman/src/agentman/agent_builder.py`

## Dependency Graph
- Hard dependencies: Python `3.11+`, `PyYAML==6.0.2`, `build==1.2.2.post1`, `pytest==8.4.1`, `pytest-cov==7.0.0`, `pip-audit==2.9.0`
- Optional dependencies: external MCP server executables referenced in generated configs

## Missing Components
- HTTP API: NOT IMPLEMENTED
- Deployment target: NOT IMPLEMENTED
- Container runtime validation in CI: NOT IMPLEMENTED
- External MCP server startup validation: NOT IMPLEMENTED
