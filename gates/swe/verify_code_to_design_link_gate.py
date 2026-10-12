"""verify_code_to_design_link_gate — SWE.3 BP3/BP4, SWE.4 BP4: code and tests ↔ the detailed design.

Under qf.yaml paths.code_dir, every code file names the unit it implements with
@unit[<unit-id>]; every unit marker, in code or tests, names a unit of the
detailed design; every unit is implemented by at least one code file; every
file with a unit marker lies in a folder named after the unit's component, at
any depth (decision 6); and every @sdoc[<REQ-UID>] names a requirement that
exists. Code and test files are told apart by the stack's code_files and
test_files (decision 14).

    python gates/swe/verify_code_to_design_link_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_requirements_tool import read_requirements  # noqa: E402
from tools.read_unit_markers_tool import (  # noqa: E402
    design_units,
    in_component_folder,
    scan_sources,
)
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402

GATE = "verify_code_to_design_link_gate"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    units = design_units(config)
    if stack is None or not units:
        return []  # the stack and detailed design gates report what is missing
    requirements = {r.text("uid") for r in read_requirements(config)} - {None}
    sources = scan_sources(config, stack)
    findings: list[Finding] = []
    implemented: set[str] = set()
    for source in sources:
        if source.kind == "code" and not source.units:
            findings.append(
                Finding(
                    "MISSING_UNIT_MARKER",
                    source.path,
                    None,
                    "This code file names no unit; add @unit[<unit-id>] for the unit it "
                    "implements.",
                )
            )
        for unit, line in source.units.items():
            if unit not in units:
                findings.append(
                    Finding(
                        "UNKNOWN_UNIT",
                        source.path,
                        line,
                        f"@unit[{unit}] names no unit of the detailed design.",
                    )
                )
                continue
            component = units[unit][0]
            if not in_component_folder(source.path, component):
                findings.append(
                    Finding(
                        "UNIT_OUTSIDE_COMPONENT",
                        source.path,
                        line,
                        f"{unit} belongs to {component}; its files lie in a folder named "
                        f"{component} (or {component.replace('-', '_')}).",
                    )
                )
            if source.kind == "code":
                implemented.add(unit)
        for uid, line in source.requirements.items():
            if uid not in requirements:
                findings.append(
                    Finding(
                        "UNKNOWN_REQUIREMENT",
                        source.path,
                        line,
                        f"@sdoc[{uid}] names no requirement.",
                    )
                )
    for unit, (component, design) in sorted(units.items()):
        if unit not in implemented:
            findings.append(
                Finding(
                    "UNIMPLEMENTED_UNIT",
                    design,
                    None,
                    f"Unit {unit} of {component} is implemented by no code file.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
