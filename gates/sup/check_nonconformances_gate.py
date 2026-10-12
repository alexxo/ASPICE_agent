"""check_nonconformances_gate — SUP.1 BP6: a fault left open is closed only with its fix.

A non-conformance is an issue labelled non-conformance whose body holds one
```yaml nonconformance block (nonconformance.v1; decision 1 of the problem
resolution stage). While a release is proposed, every closed one has its block
and names, with fixed_by, a merged pull request that fixed it
(NONCONFORMANCE_WITHOUT_FIX). Without a release there is nothing to check.

    python gates/sup/check_nonconformances_gate.py [--root PRODUCT]
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
from tools.write_release_tool import pending  # noqa: E402

GATE = "check_nonconformances_gate"


def check(config: ProductConfig) -> list[Finding]:
    if not pending(config):
        return []
    host = read_host()
    repo = repository(config.root)
    findings = []
    for issue in sorted(host.issues(repo, "non-conformance"), key=lambda i: i.number):
        if issue.state != "closed":
            continue
        where = f"#{issue.number}"
        record, why = issue.record("nonconformance")
        if record is None:
            reason = why
        elif "fixed_by" not in record:
            reason = "its block names no fixed_by"
        else:
            fix = host.pull_request(repo, record["fixed_by"])
            if fix is not None and fix.merged:
                continue
            reason = f"pull request #{record['fixed_by']} is not merged"
        findings.append(
            Finding(
                "NONCONFORMANCE_WITHOUT_FIX",
                where,
                None,
                f"Non-conformance {where} is closed, but {reason}; it closes only with the "
                "merged pull request that fixed it.",
            )
        )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
