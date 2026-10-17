"""verify_diagram_approval_gate — SWE.1 BP6: diagrams approved before requirements are derived.

While no requirement exists, there is nothing to have been approved yet, and the
gate passes — a pull request with a diagram awaiting review is not blocked. Once
requirements exist, the latest checkpoint-1 decision must be an approval of the
diagrams' current content, dated no later than the moment the first requirement
file was derived: its first commit, or now if it is not committed yet. That
moment comes from the product's git history, so outside a git repository the
order cannot be shown and the gate fails closed.

Once diagrams exist, the person reviews them on the checkpoint-1 review page:
it must exist, and while no current approval covers it, match what
agent/render_review_tool.py renders from the files now (§ 5 stages 1 and 2,
rules 22–24).

    python gates/swe/verify_diagram_approval_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.render_review_tool import review_page_findings  # noqa: E402
from tools.check_approval_order_tool import approval_order_findings  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "verify_diagram_approval_gate"


def check(config: ProductConfig) -> list[Finding]:
    folder = config.requirements_dir
    requirements = sorted(folder.rglob("*.md")) if folder.is_dir() else []
    findings = approval_order_findings(config, 1, "diagrams", requirements, "requirements")
    if any(config.diagrams_dir.glob("*.json")):
        findings += review_page_findings(config, 1)
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
