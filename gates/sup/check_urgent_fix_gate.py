"""check_urgent_fix_gate — SUP.9 BP3: an urgent fix is authorized before it merges.

The fix of a critical problem — a test naming it with @problem[<n>] — needs a
comment /authorize-urgent-fix on the problem's issue from a person in qf.yaml
urgent_approvers, given before the fix reached the main branch: on its pull
request, before now; after the merge, before the first main-branch commit that
holds the test (decision 7 of the problem resolution stage). Otherwise:
UNAUTHORIZED_URGENT_FIX. A problem without a readable record is
check_problem_record_gate's to report.

    python gates/sup/check_urgent_fix_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_commit_range_tool import reached_main  # noqa: E402
from tools.read_host_tool import read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_unit_markers_tool import problem_markers  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402

GATE = "check_urgent_fix_gate"
COMMAND = "/authorize-urgent-fix"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    named = problem_markers(config, stack) if stack else {}
    if not named:
        return []
    problems = {i.number: i for i in read_host().issues(repository(config.root), "problem")}
    findings = []
    for number, places in sorted(named.items()):
        issue = problems.get(number)
        record = issue.record("problem")[0] if issue else None
        if record is None or record.get("severity") != "critical":
            continue
        merged = reached_main(config.root, f"@problem[{number}]")
        authorized = [
            c
            for c in issue.commands(COMMAND)
            if c.author in config.urgent_approvers
            and (merged is None or datetime.fromisoformat(c.created) < merged)
        ]
        if not authorized:
            file, line = places[0]
            when = "before it reached the main branch" if merged else "before it merges"
            findings.append(
                Finding(
                    "UNAUTHORIZED_URGENT_FIX",
                    file,
                    line,
                    f"This fixes critical problem #{number}, which no person in urgent_approvers "
                    f"({', '.join(config.urgent_approvers)}) authorized with {COMMAND} {when}.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
