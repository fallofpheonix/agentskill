#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 - <<'PY'
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

docs = {
    "README.md": [
        "# agentskill",
        "## System Classification",
        "## Source of Truth",
        "## Modules",
        "## Execution Guarantees",
        "## Non-Goals",
        "## Known Limitations",
        "## Quick Start (Verified Only)",
        "## Failure Conditions",
    ],
    "backend/agentman/README.md": [
        "# agentman",
        "## System Classification",
        "## Source of Truth",
        "## Modules",
        "## Execution Guarantees",
        "## Non-Goals",
        "## Known Limitations",
        "## Quick Start (Verified Only)",
        "## Failure Conditions",
    ],
    "docs/architecture.md": [
        "# Architecture",
        "## System Topology",
        "## Modules",
        "## Orchestration Model",
        "### Agents",
        "### Stages (ENFORCED)",
        "## Data Contracts",
        "## Dependency Graph",
        "## Missing Components",
    ],
    "docs/setup.md": [
        "# Setup",
        "## Required Environment",
        "## Installation",
        "## Validation",
        "## Module Execution",
        "## Failure Modes",
        "## Non-Working Scenarios",
    ],
    "docs/ci_cd.md": [
        "# CI/CD",
        "## Pipeline Overview",
        "## Jobs",
        "### Build",
        "### Test",
        "### Security",
        "### Deploy",
        "## Failure Gates",
        "## Local Reproduction",
        "## Missing Capabilities",
    ],
    "docs/security.md": [
        "# Security",
        "## Controls",
        "## Secret Management",
        "## Dependency Security",
        "## Known Vulnerabilities",
        "## Threat Model",
        "## Gaps",
    ],
    "docs/testing.md": [
        "# Testing",
        "## Test Types",
        "## Commands",
        "## Coverage",
        "## Gaps",
        "## What Tests Prove",
        "## What Tests Do NOT Prove",
    ],
}

placeholder_pattern = re.compile(r"<[^>\n]+>")
bash_block_pattern = re.compile(r"```bash\n(.*?)\n```", re.DOTALL)

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def command_available(command: str) -> bool:
    """Check whether a command can be resolved in the current environment."""
    if shutil.which(command) is not None:
        return True
    if command == "python" and shutil.which("python3") is not None:
        return True
    return False

for relative_path, headings in docs.items():
    path = Path(relative_path)
    if not path.exists():
        fail(f"Missing documentation file: {relative_path}")
    text = path.read_text(encoding="utf-8")
    for heading in headings:
        if heading not in text:
            fail(f"Missing required heading '{heading}' in {relative_path}")
    if placeholder_pattern.search(text):
        fail(f"Placeholder text found in {relative_path}")
    if "TODO" in text or "TBD" in text:
        fail(f"Placeholder marker found in {relative_path}")

    for block in bash_block_pattern.findall(text):
        subprocess.run(["bash", "-n"], input=block, text=True, check=True)

        logical_lines = []
        current = ""
        for raw_line in block.splitlines():
            stripped = raw_line.rstrip()
            if stripped.endswith("\\"):
                current += stripped[:-1].rstrip() + " "
                continue
            current += stripped
            logical_lines.append(current)
            current = ""
        if current:
            logical_lines.append(current)

        for raw_line in logical_lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("-") or line.startswith("--"):
                continue
            command = shlex.split(line)[0]
            if command == "source":
                continue
            if not command_available(command):
                fail(f"Command '{command}' from {relative_path} is not available in PATH")

markdown_inventory = {
    str(path).replace("\\", "/")
    for path in Path(".").rglob("*.md")
    if ".venv-ci/" not in str(path).replace("\\", "/")
    and ".pytest_cache/" not in str(path).replace("\\", "/")
}
expected_inventory = set(docs)
unexpected_docs = sorted(markdown_inventory - expected_inventory)
if unexpected_docs:
    fail(f"Unexpected documentation files outside the template set: {', '.join(unexpected_docs)}")

print("Documentation validation passed.")
PY
