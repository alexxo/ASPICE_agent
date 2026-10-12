"""check_retro_actions_gate — principle #41: every lesson learned is followed up.

A retrospective action is an issue labelled retro-action whose body holds one
```yaml retro_action block (retro_action.v1): its owner and due date. While a
release is proposed, no open one lacks its block or is past its due date
(OVERDUE_RETRO_ACTION); it is closed, or rescheduled by moving its due date
(decision 11 of the problem resolution stage).

    python gates/sup/check_retro_actions_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_host_tool import read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.write_release_tool import pending  # noqa: E402

GATE = "check_retro_actions_gate"


def check(config: ProductConfig, today: date | None = None) -> list[Finding]:
    if not pending(config):
        return []
    today = today or datetime.now(timezone.utc).date()
    findings = []
    issues = read_host().issues(repository(config.root), "retro-action")
    for issue in sorted(issues, key=lambda i: i.number):
        if issue.state != "open":
            continue
        record, why = issue.record("retro_action")
        if record is None:
            reason = why
        elif date.fromisoformat(record["due"]) < today:
            reason = f"it was due {record['due']} (owner {record['owner']})"
        else:
            continue
        findings.append(
            Finding(
                "OVERDUE_RETRO_ACTION",
                f"#{issue.number}",
                None,
                f"Retrospective action #{issue.number} is open, but {reason}; close it or "
                "move its due date.",
            )
        )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
