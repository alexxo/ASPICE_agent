"""report_quality_trends_gate — SUP.1 BP5: the release reports its faults left open.

While a release is proposed, the verification report of the current tree holds
the quality section — the non-conformances opened, closed and escalated since
the previous release — written from the host's issues by
tools/write_verification_report_tool.py (MISSING_TREND_SECTION; decision 10 of
the problem resolution stage). The section is derived, so its content needs no
further check; a missing or stale report is check_verification_report_gate's.

    python gates/sup/report_quality_trends_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.write_verification_report_tool import trend_section  # noqa: E402

GATE = "report_quality_trends_gate"


def check(config: ProductConfig):
    return trend_section(config, "quality", "the non-conformances since the previous release")


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
