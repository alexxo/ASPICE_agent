"""Check that a checkpoint's approval came before the work derived from it.

Shared by every approval gate. While nothing has been derived yet there is
nothing to have been approved, and the check passes — a pull request with work
awaiting review is not blocked. Once derived work exists, the latest decision at
the checkpoint must be an approval of the current content, and the first
approval at the checkpoint must be dated no later than the moment the first
derived file appeared: its first commit, or now if it is not committed yet. A
later approval — a corrected input approved again — needs only to cover the
current content (§ 5 stages 1 and 2, rule 25). That moment is the commit's
author date, which a rebase, amend or cherry-pick keeps; it comes from git
history, so outside a git repository the order cannot be shown and the check
fails closed.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from tools.emit_findings_tool import Finding
from tools.read_approvals_tool import approval_state
from tools.read_product_config_tool import ProductConfig
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file
from tools.validate_contract_tool import validate

__all__ = ["approval_order_findings", "first_commit", "in_git"]


def approval_order_findings(
    config: ProductConfig,
    checkpoint: int,
    approves: str,
    derived: list[Path],
    derived_name: str,
) -> list[Finding]:
    """Findings when the approval at a checkpoint did not precede the derived files."""
    if not derived:
        return []
    if not in_git(config.root):
        return [
            Finding(
                "NOT_A_GIT_REPOSITORY",
                ".",
                None,
                f"{derived_name.capitalize()} exist but the product is not a git "
                "repository, so when they were derived cannot be shown against the "
                f"checkpoint-{checkpoint} approval.",
            )
        ]
    state = approval_state(config, checkpoint, approves)
    if state.status in ("missing", "changes_requested", "invalid"):
        return [
            Finding(
                "MISSING_APPROVAL",
                config.relative(config.approvals_dir),
                None,
                f"{derived_name.capitalize()} exist, but the {approves} are not approved "
                f"at checkpoint {checkpoint}: {state.reason}.",
            )
        ]
    shown = config.relative(state.path)
    if state.status == "outdated":
        return [
            Finding(
                "APPROVAL_OUTDATED",
                shown,
                None,
                f"The checkpoint-{checkpoint} approval covers older {approves} — "
                f"{state.reason}; the current ones need approving.",
            )
        ]
    first = min(first_commit(config.root, f) for f in derived)
    approved, approval = _first_approval(config, checkpoint, approves) or (state.date, state.path)
    if approved > first:
        return [
            Finding(
                "APPROVED_TOO_LATE",
                config.relative(approval),
                None,
                f"The {approves} were first approved at {approved.isoformat()}, after the "
                f"first of the {derived_name} appeared at {first.isoformat()}; they are "
                f"derived from approved {approves} only.",
            )
        ]
    return []


def _first_approval(
    config: ProductConfig, checkpoint: int, approves: str
) -> tuple[datetime, Path] | None:
    """The date and file of the earliest approval at the checkpoint."""
    pattern = f"*-checkpoint-{checkpoint}-{approves}.yaml"
    for path in sorted(config.approvals_dir.glob(pattern)):
        try:
            data = read_yaml_file(path)
        except YamlReadError:
            continue
        if not validate(data, "approval") and data["decision"] == "approved":
            return datetime.fromisoformat(data["date"].replace("Z", "+00:00")), path
    return None


def in_git(root: Path) -> bool:
    run = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return run.returncode == 0 and run.stdout.strip() == "true"


def first_commit(root: Path, file: Path) -> datetime:
    """When the file was first committed, or now if it never was."""
    run = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "log",
            "--diff-filter=A",
            "--follow",
            "--format=%aI",
            "--",
            str(file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    dates = run.stdout.split()
    if run.returncode != 0 or not dates:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(dates[-1])
