"""verify_stack_approval_gate — SWE.2: the stack approved at checkpoint 3 before components exist.

While no component is designed, nothing has to be approved yet. Once the
architecture files exist, the latest checkpoint-3 decision must approve the
current stack and its decision record, dated before the first architecture file
appeared (from git history).

    python gates/swe/verify_stack_approval_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.check_approval_order_tool import approval_order_findings  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "verify_stack_approval_gate"


def check(config: ProductConfig) -> list[Finding]:
    folder = config.architecture_dir
    components = sorted(folder.glob("*.md")) if folder.is_dir() else []
    return approval_order_findings(config, 3, "stack", components, "architecture files")


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
