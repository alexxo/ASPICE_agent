"""verify_change_approval_gate — SUP.10 BP3: no change is built before it is approved.

A commit builds change request #<n> when its message names #<n> and #<n> is an
issue labelled change-request (decision 1 of the change request stage). Every
change request a commit of the history names has a /approve-change comment from
a person in qf.yaml change_approvers, given before the first commit that names
it (UNAPPROVED_CHANGE; decision 2). That the change then follows checkpoints 1
and 2 is their gates' to check.

    python gates/sup/verify_change_approval_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_commit_range_tool import issue_mentions  # noqa: E402
from tools.read_host_tool import read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "verify_change_approval_gate"
COMMAND = "/approve-change"


def check(config: ProductConfig) -> list[Finding]:
    named = issue_mentions(config.root, "HEAD")
    if not named:
        return []
    changes = read_host().issues(repository(config.root), "change-request")
    findings = []
    for change in sorted(changes, key=lambda i: i.number):
        dates = named.get(change.number)
        if not dates:
            continue
        signed = [
            c
            for c in change.commands(COMMAND)
            if c.author in config.change_approvers and datetime.fromisoformat(c.created) < dates[0]
        ]
        if not signed:
            findings.append(
                Finding(
                    "UNAPPROVED_CHANGE",
                    f"#{change.number}",
                    None,
                    f"Change request #{change.number} is built by commits since "
                    f"{dates[0]:%Y-%m-%d %H:%M}, but no person in change_approvers "
                    f"({', '.join(config.change_approvers)}) gave {COMMAND} before them.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
