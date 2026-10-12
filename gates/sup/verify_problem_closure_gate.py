"""verify_problem_closure_gate — SUP.9 BP5, BP6: closed with its fix and its finder's word.

On every pull request, every @problem[<n>] marker names an issue labelled
problem (UNKNOWN_PROBLEM). While a release is proposed, a problem marked fixed
or closed has a test that names it (MISSING_PROBLEM_TEST), and a closed one has
it on the main branch (CLOSED_WITHOUT_FIX) — unless it names the change request
that carries its fix (decision 9 of the problem resolution stage); a closed one
also has a
/confirm-fixed comment from its reporter — the issue's author — given after the
fix reached the main branch (MISSING_CONFIRMATION, decisions 7 and 8). That the
test passes is the suites' gates' to check. A problem without a readable record
is check_problem_record_gate's to report.

    python gates/sup/verify_problem_closure_gate.py [--root PRODUCT]
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
from tools.write_release_tool import pending  # noqa: E402

GATE = "verify_problem_closure_gate"
COMMAND = "/confirm-fixed"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    named = problem_markers(config, stack) if stack else {}
    release = bool(pending(config))
    if not named and not release:
        return []
    problems = {i.number: i for i in read_host().issues(repository(config.root), "problem")}
    findings = []
    for number, places in sorted(named.items()):
        if number not in problems:
            for file, line in places:
                findings.append(
                    Finding(
                        "UNKNOWN_PROBLEM",
                        file,
                        line,
                        f"@problem[{number}] names no issue labelled problem.",
                    )
                )
    if release:
        for number, issue in sorted(problems.items()):
            findings += _closure(config, number, issue, number in named)
    return findings


def _closure(config: ProductConfig, number: int, issue, tested: bool) -> list[Finding]:
    record, _why = issue.record("problem")
    if record is None:
        return []
    where = f"#{number}"
    findings = []
    carried = "change_request" in record  # the change desk carries the fix (decision 9)
    if record["status"] in ("fixed", "closed") and not tested and not carried:
        findings.append(
            Finding(
                "MISSING_PROBLEM_TEST",
                where,
                None,
                f"Problem {where} is {record['status']}, but no test names it with "
                f"@problem[{number}]; the crack bench proves the fix.",
            )
        )
    if issue.state != "closed":
        return findings
    merged = reached_main(config.root, f"@problem[{number}]")
    if merged is None and not carried:
        findings.append(
            Finding(
                "CLOSED_WITHOUT_FIX",
                where,
                None,
                f"Problem {where} is closed, but its test is not on the main branch and it "
                "names no change request.",
            )
        )
    confirmed = [
        c
        for c in issue.commands(COMMAND)
        if c.author == issue.author
        and (merged is None or datetime.fromisoformat(c.created) >= merged)
    ]
    if not confirmed:
        findings.append(
            Finding(
                "MISSING_CONFIRMATION",
                where,
                None,
                f"Problem {where} is closed without {COMMAND} from its reporter "
                f"({issue.author}) after the fix.",
            )
        )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
