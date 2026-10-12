"""check_problem_record_gate — SUP.9 BP1, BP2, BP4: every problem recorded, analysed, announced.

A problem is an issue labelled problem whose body holds one ```yaml problem
block (problem.v1; decision 1 of the problem resolution stage). On every pull
request, every problem a test names with @problem[<n>] — one being fixed — has
its block (INCOMPLETE_PROBLEM_RECORD) and its analysis: cause, impact and
severity (MISSING_ANALYSIS), so it is analysed before its fix merges (decision
2). While a release is proposed, every problem is checked: its block, its
analysis once past the open status, and for a high or critical one its affected
parties and the date they were notified (MISSING_ALERT). That a test names a
problem that exists is verify_problem_closure_gate's.

    python gates/sup/check_problem_record_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_host_tool import read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_unit_markers_tool import problem_markers  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402
from tools.write_release_tool import pending  # noqa: E402

GATE = "check_problem_record_gate"
ANALYSIS = ("cause", "impact", "severity")


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    named = problem_markers(config, stack) if stack else {}
    release = bool(pending(config))
    if not named and not release:
        return []
    problems = {i.number: i for i in read_host().issues(repository(config.root), "problem")}
    wanted = set(problems) if release else set(named) & set(problems)
    findings = []
    for number in sorted(wanted):
        record, why = problems[number].record("problem")
        where = f"#{number}"
        if record is None:
            findings.append(
                Finding("INCOMPLETE_PROBLEM_RECORD", where, None, f"Problem {where}: {why}.")
            )
            continue
        missing = [field for field in ANALYSIS if field not in record]
        if missing and (record["status"] != "open" or number in named):
            state = "is named by a test" if number in named else f"is {record['status']}"
            findings.append(
                Finding(
                    "MISSING_ANALYSIS",
                    where,
                    None,
                    f"Problem {where} {state} but states no {', '.join(missing)}; analyse it "
                    "before it is fixed.",
                )
            )
        bad = record.get("severity") in ("high", "critical")
        if release and bad and not ("affected_parties" in record and "notified" in record):
            findings.append(
                Finding(
                    "MISSING_ALERT",
                    where,
                    None,
                    f"Problem {where} is {record['severity']} but does not name its affected "
                    "parties and when they were notified.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
