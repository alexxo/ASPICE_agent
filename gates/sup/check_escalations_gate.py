"""check_escalations_gate — SUP.1 BP7: no fault left open is forgotten.

While a release is proposed, every open non-conformance older than qf.yaml
escalate_after_days — counted from its issue's creation (decision 11 of the
problem resolution stage) — is labelled escalated and assigned to a person who
can decide (UNESCALATED_NONCONFORMANCE). That the escalation leads to a decision
is left to the organisation.

    python gates/sup/check_escalations_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_host_tool import read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.write_release_tool import pending  # noqa: E402

GATE = "check_escalations_gate"


def check(config: ProductConfig, now: datetime | None = None) -> list[Finding]:
    if not pending(config):
        return []
    now = now or datetime.now(timezone.utc)
    limit = timedelta(days=config.escalate_after_days)
    findings = []
    issues = read_host().issues(repository(config.root), "non-conformance")
    for issue in sorted(issues, key=lambda i: i.number):
        age = now - datetime.fromisoformat(issue.created)
        if issue.state != "open" or age <= limit:
            continue
        missing = [] if "escalated" in issue.labels else ["the label escalated"]
        missing += [] if issue.assignees else ["an assignee"]
        if missing:
            findings.append(
                Finding(
                    "UNESCALATED_NONCONFORMANCE",
                    f"#{issue.number}",
                    None,
                    f"Non-conformance #{issue.number} has been open {age.days} days, more than "
                    f"{config.escalate_after_days}, without {' and '.join(missing)}.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
