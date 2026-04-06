# Migration Map

| Old Path | New Path | Rationale |
| --- | --- | --- |
| `awesome-opencode` | `docs/awesome-opencode` | Registry tooling and curated catalog belong to the documentation plane. |
| `specific/agentman` | `backend/agentman` | Executable Python CLI and builder are backend/control-plane code. |
| `open-antigravity` | `frontend/open-antigravity` | Product-facing UI specification and local proxy are grouped under the frontend surface. |
| `codex-develop` | `infra/codex-develop` | Shell automation for external environments belongs to infrastructure tooling. |
| `specific/agentman/examples/tri-engine-cicd` | `system/tri-engine` | Repo-level orchestration is a system artifact, not a backend example fixture. |
| `awesome-opencode/.github/PULL_REQUEST_TEMPLATE.md` | `.github/PULL_REQUEST_TEMPLATE.md` | PR policy is now repo-root state. |
| `awesome-opencode/.github/workflows/*` | `.github/workflows/tri-engine-ci.yml` | Subproject-local CI was replaced with one repo-level pipeline. |
| `.DS_Store`, `__pycache__/*` | removed | Local machine artifacts are not reproducible repository content. |
