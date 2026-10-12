"""check_testability_gate — principle #15: the architecture declares how to test in isolation.

Every ```yaml component block of role component under paths.architecture_dir
declares its composition_root, and every ```yaml interface block declares the
implementations of its 'to' end — a real one and a test double. Only presence is
checked here: a block that cannot be read or breaks its contract is reported by
check_design_contract_gate, so one cause gives one finding.

    python gates/swe/check_testability_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "check_testability_gate"


def check(config: ProductConfig) -> list[Finding]:
    folder = config.architecture_dir
    files = sorted(folder.glob("*.md")) if folder.is_dir() else []
    findings: list[Finding] = []
    seen = False
    for path in files:
        shown = config.relative(path)
        for tag, field, rule, what in (
            ("component", "composition_root", "MISSING_COMPOSITION_ROOT", "its composition root"),
            (
                "interface",
                "implementations",
                "MISSING_IMPLEMENTATIONS",
                "a real implementation and a test double",
            ),
        ):
            for block in read_yaml_blocks(path, tag):
                seen = True
                data = block.data
                if block.error or not isinstance(data, dict):
                    continue
                if tag == "component" and data.get("role") != "component":
                    continue
                if field not in data:
                    findings.append(
                        Finding(
                            rule,
                            shown,
                            block.line,
                            f"{tag.capitalize()} {data.get('id')} does not declare {what}.",
                        )
                    )
    if not seen:
        return [
            Finding(
                "NO_ARCHITECTURE",
                config.relative(folder),
                None,
                "No component or interface found; the architecture belongs here.",
            )
        ]
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
