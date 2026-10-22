"""verify_requirements_approval_gate — SWE.1: requirements approved at checkpoint 2 before design.

While no design work exists, nothing has to be approved yet. Once the stack,
an architecture file or a detailed-design file exists, the latest checkpoint-2
decision must approve the current requirements, glossary and the diagrams they
are derived from, and the first approval at checkpoint 2 must be dated before
the first of those files appeared (from git history): a changed diagram
withdraws the approval, and approving again restores it.

Once requirements exist, the person reviews them on the review page: it must
exist, and while no current approval covers it, match what
agent/render_review_tool.py renders from the files now (§ 5 stages 1 and 2,
rules 22–25).

    python gates/swe/verify_requirements_approval_gate.py [--root PRODUCT]
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

GATE = "verify_requirements_approval_gate"


def check(config: ProductConfig) -> list[Finding]:
    folder = config.architecture_dir
    derived = sorted(folder.glob("*.md")) if folder.is_dir() else []
    if config.stack_file.is_file():
        derived.append(config.stack_file)
    design = config.detailed_design_dir
    if design.is_dir():
        derived += sorted(p for p in design.iterdir() if p.suffix in (".md", ".json"))
    findings = approval_order_findings(
        config, 2, "requirements", derived, "stack, architecture and detailed-design files"
    )
    folder = config.requirements_dir
    if folder.is_dir() and any(folder.rglob("*.md")):
        findings += review_page_findings(config)
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
