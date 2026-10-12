"""verify_branch_protection_gate — SUP.8 BP3, BP4: the main branch's history cannot be rewritten.

The default branch, read from the host, refuses force-pushes (FORCE_PUSH_ALLOWED)
and its own deletion (DELETION_ALLOWED), so every past state of every
configuration item stays recoverable. That changes arrive only through reviewed
pull requests is verify_required_checks_gate's (SUP.1).

    python gates/sup/verify_branch_protection_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_host_tool import read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "verify_branch_protection_gate"


def check(config: ProductConfig) -> list[Finding]:
    host = read_host()
    repo = repository(config.root)
    branch = host.default_branch(repo)
    protection = host.protection(repo, branch)
    findings = []
    if protection is None or protection.allow_force_pushes:
        findings.append(
            Finding(
                "FORCE_PUSH_ALLOWED",
                ".",
                None,
                f"Branch {branch} of {repo} accepts force-pushes, which rewrite agreed history; "
                "disable them in its branch protection.",
            )
        )
    if protection is None or protection.allow_deletions:
        findings.append(
            Finding(
                "DELETION_ALLOWED",
                ".",
                None,
                f"Branch {branch} of {repo} can be deleted; disable deletions in its branch "
                "protection.",
            )
        )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
