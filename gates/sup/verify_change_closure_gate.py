"""verify_change_closure_gate — SUP.10 BP5, BP6: a change closed only once built and confirmed.

While a release is proposed, every closed change request has a commit naming it
on the main branch (CLOSED_WITHOUT_IMPLEMENTATION) and a /confirm-change comment
from its initiator — the issue's author — given after the last such commit
(MISSING_CHANGE_CONFIRMATION; decision 7 of the change request stage); and the
verification report of the current tree lists the change requests the release
implements and those still open (MISSING_CHANGE_SECTION; decision 8). Without a
release there is nothing to check.

    python gates/sup/verify_change_closure_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_commit_range_tool import issue_mentions, main_ref  # noqa: E402
from tools.read_host_tool import read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.write_release_tool import pending  # noqa: E402
from tools.write_verification_report_tool import trend_section  # noqa: E402

GATE = "verify_change_closure_gate"
COMMAND = "/confirm-change"


def check(config: ProductConfig) -> list[Finding]:
    if not pending(config):
        return []
    main = main_ref(config.root)
    on_main = issue_mentions(config.root, main) if main else {}
    findings = []
    for change in sorted(
        read_host().issues(repository(config.root), "change-request"), key=lambda i: i.number
    ):
        if change.state != "closed":
            continue
        where = f"#{change.number}"
        dates = on_main.get(change.number)
        if not dates:
            findings.append(
                Finding(
                    "CLOSED_WITHOUT_IMPLEMENTATION",
                    where,
                    None,
                    f"Change request {where} is closed, but no commit on the main branch names it.",
                )
            )
        confirmed = [
            c
            for c in change.commands(COMMAND)
            if c.author == change.author
            and (not dates or datetime.fromisoformat(c.created) >= dates[-1])
        ]
        if not confirmed:
            findings.append(
                Finding(
                    "MISSING_CHANGE_CONFIRMATION",
                    where,
                    None,
                    f"Change request {where} is closed without {COMMAND} from its initiator "
                    f"({change.author}) after its last commit.",
                )
            )
    findings += trend_section(
        config, "changes", "the change requests it implements", "MISSING_CHANGE_SECTION"
    )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
