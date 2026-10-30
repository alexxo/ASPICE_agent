"""Check that a checkpoint's approval came before the work derived from it.

Shared by every approval gate. While nothing has been derived yet there is
nothing to have been approved, and the check passes — a pull request with work
awaiting review is not blocked. Once derived work exists, the latest decision at
the checkpoint must be an approval of the current content. The order follows
from the flow: the checkpoint's pull request is merged once the architect
approved it, and the derived work starts on the main branch after it
(record_checkpoint_tool). Approvals are read from git history, so outside a git
repository none can be shown and the check fails closed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tools.emit_findings_tool import Finding
from tools.read_approvals_tool import approval_state
from tools.read_product_config_tool import ProductConfig

__all__ = ["approval_order_findings", "in_git"]


def approval_order_findings(
    config: ProductConfig,
    checkpoint: int,
    approves: str,
    derived: list[Path],
    derived_name: str,
) -> list[Finding]:
    """Findings when derived files exist without a current approval at the checkpoint."""
    if not derived:
        return []
    if not in_git(config.root):
        return [
            Finding(
                "NOT_A_GIT_REPOSITORY",
                ".",
                None,
                f"{derived_name.capitalize()} exist but the product is not a git "
                f"repository, so the checkpoint-{checkpoint} approval cannot be read.",
            )
        ]
    state = approval_state(config, checkpoint, approves)
    if state.status == "missing":
        return [
            Finding(
                "MISSING_APPROVAL",
                ".",
                None,
                f"{derived_name.capitalize()} exist, but the {approves} are not approved "
                f"at checkpoint {checkpoint}: {state.reason}.",
            )
        ]
    if state.status == "outdated":
        return [
            Finding(
                "APPROVAL_OUTDATED",
                ".",
                None,
                f"The checkpoint-{checkpoint} approval covers older {approves} — "
                f"{state.reason}; the current ones need approving.",
            )
        ]
    return []


def in_git(root: Path) -> bool:
    run = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return run.returncode == 0 and run.stdout.strip() == "true"
