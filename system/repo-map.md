# Repository Map

## Component Classification

| Path | Role | Entry points | Dependencies | Classification |
| --- | --- | --- | --- | --- |
| `docs/awesome-opencode` | Curated registry generator for Opencode plugins, themes, agents, projects, and resources | `package.json`, `scripts/generate-readme.js`, `scripts/validate.js`, `scripts/export-json.js` | Node.js 20, `ajv`, `ajv-formats`, `glob`, `js-yaml` | `KEEP` core data model, `MODIFY` CI integration and script hygiene |
| `backend/agentman` | Python CLI and builder for Agentfile-driven agent containers | `pyproject.toml`, `src/agentman/__main__.py`, `Makefile`, `docker/Dockerfile.base` | Python 3.10+, `fast-agent-mcp`, `PyYAML`, Docker, optional framework deps emitted at generation time | `KEEP` parser/builder core, `MODIFY` packaging, imports, examples, and tests |
| `frontend/open-antigravity` | Product/design specification plus local proxy proof-of-concept | `mitmserver/package.json`, `mitmserver/server.js` | Node.js 20, `http-proxy` | `KEEP` design docs, `MODIFY` proxy hardening and README accuracy |
| `infra/codex-develop` | External repository bootstrap and compose orchestration scripts for NUM-CODEX environments | `gitUpdate.sh`, `start-develop.sh`, `stop-develop.sh`, `down-develop.sh`, `rebuild-develop.sh` | Bash, Docker Compose, external NUM-CODEX repositories | `KEEP` orchestration role, `MODIFY` shell/runtime correctness and error handling |
| `.github/workflows` | Repo-root CI/CD control plane | `tri-engine-ci.yml` | GitHub Actions, Python, Node.js | `REPLACE` subproject-local workflow fragments with a single repo pipeline |
| `.DS_Store`, `__pycache__` | Tracked local machine artifacts | none | none | `DELETE` |

## Dependency Graph

```text
system/tri-engine
  -> backend/agentman/src/agentman/agentfile_parser.py
  -> backend/agentman/src/agentman/agent_builder.py

backend/agentman
  -> fast-agent-mcp
  -> PyYAML
  -> generated Fast-Agent or Agno runtime files
  -> Docker (for build/run commands)

docs/awesome-opencode
  -> scripts/utils/yaml.js
  -> scripts/utils/validation.js
  -> scripts/utils/template.js
  -> dist/registry.json

frontend/open-antigravity/mitmserver
  -> http-proxy

infra/codex-develop
  -> Docker Compose or docker compose
  -> external NUM-CODEX repositories cloned at runtime
```

## Conflict List

1. The repository started as four unrelated top-level modules with no repo-root control plane.
2. `backend/agentman` imported the full CLI/build stack from `__init__.py`, causing package import to fail when undeclared runtime dependencies were absent.
3. `backend/agentman` required `yaml` at runtime but did not declare `PyYAML`.
4. `backend/agentman` examples embedded inline credential placeholders (`sk-...`, `ghp_...`) and mixed secure references with literal tokens.
5. `backend/agentman/tests/test_framework_support.py` imported from `src.agentman`, diverging from the installed package path.
6. `infra/codex-develop` shell scripts declared `/bin/sh` while using Bash-only parameter expansion and `==` tests.
7. `infra/codex-develop/start-develop.sh` assumed external repositories and ontology assets existed, then copied blindly.
8. `frontend/open-antigravity/README.md` claimed a runnable Docker Compose stack that does not exist in this checkout.
9. `frontend/open-antigravity/mitmserver/server.js` logged raw request and response headers, including potential credentials.
10. `docs/awesome-opencode/package.json` referenced a nonexistent `scripts/bootstrap.js`.
11. CI/CD existed only as subproject-local `awesome-opencode` workflows; there was no integrated build-test-security-deploy pipeline for the monorepo.

## Refactor Plan

1. Normalize layout into `/frontend`, `/backend`, `/docs`, `/infra`, `/system`, `/security`, `/ci_cd`, and `/tests`.
2. Preserve each module in place under the new layout instead of rewriting it.
3. Convert repo-level orchestration into `system/tri-engine/Agentfile` and `system/tri-engine/prompt.txt`.
4. Replace local workflow fragments with one root pipeline that builds docs, tests `agentman`, runs syntax checks, audits Node dependencies, scans secrets, and auto-regenerates published registry artifacts on `main`.
5. Remove tracked local artifacts and inline credential placeholders.
