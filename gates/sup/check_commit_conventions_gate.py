"""check_commit_conventions_gate — SUP.8 BP4: commits and branches named by convention.

Every non-merge commit of the pull request (base..HEAD) is a Conventional
Commit, type(scope)?!?: subject (NOT_CONVENTIONAL), and names the requirement
or issue it serves — REQ-<n> or #<n> — in its header or body
(MISSING_REQUIREMENT_TOKEN); a revert git wrote (Revert "...") is exempt. Only
the branch names that carry meaning are checked: arch/<slug> on the
architecture track and checkpoint/<n> for a checkpoint's work, the release's
(checkpoint 5) included (BAD_BRANCH_NAME); any
other name is free, since every commit names its reason (decision 3 of the
configuration management stage). On a push to the main branch the commits it
adds are checked the same way, so a commit that reached it without a pull
request still names its reason (decision 8 of the configuration management
stage).
Main's check-commit-message, check-commit-range and check-branch-name, as one
gate.

    python gates/sup/check_commit_conventions_gate.py [--root PRODUCT] [--base REF]
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.check_approval_order_tool import in_git  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_commit_range_tool import branch, main_push, resolve_base  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "check_commit_conventions_gate"
TYPES = (
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
)
CONVENTIONAL = re.compile(rf"^({'|'.join(TYPES)})(\([^)\s]+\))?!?: \S")
TOKEN = re.compile(r"\bREQ-[0-9]{4,}\b|(?<![\w&])#[0-9]+\b")
_SLUG = r"[a-z0-9]+(-[a-z0-9]+)*"
# The branch names that carry meaning: prefix → (the form it must have, shown).
BRANCHES = {
    "arch/": (re.compile(rf"^arch/{_SLUG}$"), "arch/<slug>, e.g. arch/session-store"),
    "checkpoint/": (re.compile(r"^checkpoint/[1235]$"), "checkpoint/<n>, n 1, 2, 3 or 5"),
}


def check(config: ProductConfig, base: str | None = None) -> list[Finding]:
    root = config.root
    if not in_git(root):
        return [
            Finding(
                "NOT_A_GIT_REPOSITORY",
                ".",
                None,
                "The product is not a git repository, so its commits cannot be checked.",
            )
        ]
    findings = []
    name = branch(root) or ""
    for prefix, (form, shown) in BRANCHES.items():
        if name.startswith(prefix) and not form.match(name):
            findings.append(
                Finding(
                    "BAD_BRANCH_NAME",
                    ".",
                    None,
                    f"Branch '{name}' starts with {prefix}, so it must be {shown}.",
                )
            )
    push = main_push() if base is None else None
    start = push.before if push and push.before else resolve_base(root, base)
    span = f"{start}..HEAD" if start else "HEAD"
    shas = _git(root, "rev-list", "--no-merges", "--reverse", span).split()
    for sha in shas:
        message = _git(root, "log", "-1", "--format=%B", sha).strip()
        header = message.splitlines()[0] if message else ""
        if header.startswith('Revert "'):
            continue
        if not CONVENTIONAL.match(header):
            findings.append(
                Finding(
                    "NOT_CONVENTIONAL",
                    ".",
                    None,
                    f"Commit {sha[:7]} '{header}' is not a Conventional Commit: "
                    f"type(scope)?: subject, with type one of {', '.join(TYPES)}.",
                )
            )
        if not TOKEN.search(message):
            findings.append(
                Finding(
                    "MISSING_REQUIREMENT_TOKEN",
                    ".",
                    None,
                    f"Commit {sha[:7]} '{header}' names no requirement or issue; add the "
                    "REQ-<n> or #<n> it serves to its header or body.",
                )
            )
    return findings


def _git(root: Path, *args: str) -> str:
    run = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return run.stdout if run.returncode == 0 else ""


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
