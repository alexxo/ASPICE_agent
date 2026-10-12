"""report_problem_trends_gate — SUP.9 BP7: the release reports its problems.

While a release is proposed, the verification report of the current tree holds
the problem section — the problems opened, fixed and still open since the
previous release, by severity and by component — written from the host's issues
by tools/write_verification_report_tool.py (MISSING_TREND_SECTION; decision 10
of the problem resolution stage). The section is derived, so its content needs
no further check; a missing or stale report is check_verification_report_gate's.

    python gates/sup/report_problem_trends_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.write_verification_report_tool import trend_section  # noqa: E402

GATE = "report_problem_trends_gate"


def check(config: ProductConfig):
    return trend_section(config, "problems", "the problems since the previous release")


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
