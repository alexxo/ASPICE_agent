"""verify_code_to_design_link_gate — SWE.3 BP3/BP4, SWE.4 BP4: code and tests ↔ the detailed design.

Under qf.yaml paths.code_dir, every code file names the unit it implements with
@unit[<unit-id>], except two that implement none: the file of a component's
composition_root, named by the architecture and approved at checkpoint 3 —
where the concrete implementations are wired, outside the component's folder if
the architecture puts it there — and a file that holds no code (empty, or a
Python package's __init__.py with a docstring alone). Every unit marker, in
code or tests, names a unit of the detailed design; every unit is implemented
by at least one code file; every file with a unit marker lies in a folder named
after the unit's component, at any depth (decision 6); and every
@sdoc[<REQ-UID>] names a requirement that exists. Code and test files are told
apart by the stack's code_files and test_files (decision 14).

    python gates/swe/verify_code_to_design_link_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import ast
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
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402

GATE = "verify_code_to_design_link_gate"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    units = design_units(config)
    if stack is None or "unit" not in stack["suites"] or not units:
        return []  # the stack, plan and detailed design gates report what is missing
    requirements = {r.text("uid") for r in read_requirements(config)} - {None}
    sources = scan_sources(config, stack)
    roots = composition_roots(config)
    findings: list[Finding] = []
    implemented: set[str] = set()
    for source in sources:
        exempt = is_composition_root(source.path, roots) or holds_no_code(config, source.path)
        if source.kind == "code" and not source.units and not exempt:
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


def composition_roots(config: ProductConfig) -> list[tuple[str, ...]]:
    """Every component's composition_root, as its dotted parts."""
    folder = config.architecture_dir
    roots = []
    for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        for block in read_yaml_blocks(path, "component"):
            data = block.data if isinstance(block.data, dict) else {}
            root = data.get("composition_root")
            if data.get("role") == "component" and isinstance(root, str) and root.strip():
                roots.append(tuple(root.strip().replace(":", ".").split(".")))
    return roots


def is_composition_root(path: str, roots: list[tuple[str, ...]]) -> bool:
    """The file a composition_root names: its path ends with the root's module
    (the root without its function, e.g. pkg/__main__.py for pkg.__main__.main),
    or with the whole root."""
    parts = Path(path).with_suffix("").parts
    for root in roots:
        for module in (root[:-1], root):
            if module and parts[-len(module) :] == module:
                return True
    return False


def holds_no_code(config: ProductConfig, path: str) -> bool:
    """Empty, or Python with nothing but a docstring: a package's __init__.py."""
    try:
        text = (config.root / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if not text.strip():
        return True
    if not path.endswith(".py"):
        return False
    try:
        body = ast.parse(text).body
    except SyntaxError:
        return False
    return all(
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
        for node in body
    )


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
