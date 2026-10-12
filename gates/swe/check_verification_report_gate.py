"""check_verification_report_gate — SWE.4 BP5, SWE.5 BP7, SWE.6 BP5: the report is current.

The verification report written by tools/write_verification_report_tool.py
exists for the current tree, under .qf/runs/<tree-hash>/ (MISSING_REPORT), and
every suite run of the stack it was written from is the one kept for the tree,
unchanged (STALE_REPORT). The report is derived, so its content needs no
further check (decision 8 of the software verification stage). That it is kept
for every release is verify_release_evidence_gate's.

    python gates/swe/check_verification_report_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import kept_run, read_stack, tree_key  # noqa: E402
from tools.write_verification_report_tool import (  # noqa: E402
    REPORT,
    report_dir,
    suite_digest,
    verification_suites,
)

GATE = "check_verification_report_gate"
WRITE = "python tools/write_verification_report_tool.py"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    if stack is None:
        return []  # check_stack_decision_gate reports a missing or broken stack
    folder = report_dir(config)
    if folder is None:
        return [
            Finding(
                "MISSING_REPORT",
                ".",
                None,
                "The product is not a git repository, so no report can be kept for its tree.",
            )
        ]
    path = folder / REPORT
    shown = config.relative(path)
    if not path.is_file():
        return [
            Finding(
                "MISSING_REPORT",
                shown,
                None,
                f"No verification report for the current tree; write it with {WRITE}.",
            )
        ]
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        inputs = dict(report["inputs"])
    except (ValueError, KeyError, TypeError):
        return [
            Finding(
                "STALE_REPORT",
                shown,
                None,
                f"The report is unreadable; write it again with {WRITE}.",
            )
        ]
    key = tree_key(config.root)
    findings = []
    suites = verification_suites(stack)
    for name in sorted(set(suites) | set(inputs)):
        kept = kept_run(config, key, "suites", name) if name in suites else None
        if kept is None or inputs.get(name) != suite_digest(kept):
            findings.append(
                Finding(
                    "STALE_REPORT",
                    shown,
                    None,
                    f"The report was not written from the {name} suite's current run; "
                    f"write it again with {WRITE}.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
