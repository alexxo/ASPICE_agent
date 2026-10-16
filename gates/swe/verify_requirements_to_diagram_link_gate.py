"""verify_requirements_to_diagram_link_gate — SWE.1 BP1/BP5: requirements ↔ diagrams.

Both directions:
- every requirement's derived_from names a diagram element that exists, or — for
  a constraint — a wish that exists;
- every node, edge and invariant of every diagram is covered by at least one
  requirement of the diagram's level. Messages produce acceptance criteria, not
  requirements, so they need no requirement of their own.

A diagram's level is set by its type: a sequence diagram is software level, any
other type system level. A requirement derives from a diagram of its own level
(LEVEL_MISMATCH), and only then covers the element.

A diagram the adapter cannot read faithfully is reported once
(DIAGRAM_UNREADABLE) and its links are not checked: the adapter's detailed
problems belong to check_diagram_contract_gate.

    python gates/swe/verify_requirements_to_diagram_link_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.read_archify_diagram_adapter import read_archify_diagrams  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_requirements_tool import read_requirements  # noqa: E402
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "verify_requirements_to_diagram_link_gate"
WISH = re.compile(r"^W-[0-9]+$")
COVERED_KINDS = ("node", "edge", "invariant")
LEVELS = ("system", "software")


def check(config: ProductConfig) -> list[Finding]:
    findings: list[Finding] = []
    results = read_archify_diagrams(config.diagrams_dir, config.root)
    if not results:
        findings.append(
            Finding(
                "NO_DIAGRAMS",
                config.relative(config.diagrams_dir),
                None,
                "No diagram found; requirements are derived from approved diagrams.",
            )
        )
    diagrams: dict[str, dict] = {}
    unreadable: set[str] = set()
    for path, result in results:
        diagram_id = path.name.split(".", 1)[0]
        if result.diagram is None or result.problems:
            unreadable.add(diagram_id)
            findings.append(
                Finding(
                    "DIAGRAM_UNREADABLE",
                    config.relative(path),
                    None,
                    f"Diagram '{diagram_id}' cannot be read faithfully ({len(result.problems)} "
                    "problem(s)); its links are not checked. check_diagram_contract_gate "
                    "lists the problems.",
                )
            )
        else:
            diagrams[diagram_id] = result.diagram

    wishes = _wish_ids(config)
    covered: set[tuple[str, str]] = set()
    for req in read_requirements(config):
        target = req.text("derived_from")
        if target is None:
            continue  # a missing or malformed field is check_requirements_contract_gate's
        uid = req.text("uid") or "A requirement"
        line = req.line("derived_from")
        if WISH.match(target):
            if target not in wishes:
                findings.append(
                    Finding(
                        "UNKNOWN_WISH",
                        req.file,
                        line,
                        f"{uid} derives from {target}, which is not in the wishes file.",
                    )
                )
            continue
        if "#" not in target:
            continue
        diagram_id, element_id = target.split("#", 1)
        if diagram_id in unreadable:
            continue
        diagram = diagrams.get(diagram_id)
        if diagram is None:
            findings.append(
                Finding(
                    "UNKNOWN_DIAGRAM",
                    req.file,
                    line,
                    f"{uid} derives from diagram '{diagram_id}', which does not exist.",
                )
            )
        elif element_id not in {e["id"] for e in diagram["elements"]}:
            findings.append(
                Finding(
                    "UNKNOWN_ELEMENT",
                    req.file,
                    line,
                    f"{uid} derives from {target}, but diagram '{diagram_id}' declares no "
                    f"element '{element_id}'; use an existing element ID.",
                )
            )
        elif req.text("level") in LEVELS and req.text("level") != _level(diagram):
            findings.append(
                Finding(
                    "LEVEL_MISMATCH",
                    req.file,
                    req.line("level"),
                    f"{uid} is {req.text('level')} level but derives from {target}, an element "
                    f"of a {_level(diagram)}-level diagram ({diagram['type']}); a "
                    "system-level requirement derives from a system-level diagram, a "
                    "software-level one from a sequence diagram.",
                )
            )
        else:
            covered.add((diagram_id, element_id))

    for diagram_id, diagram in sorted(diagrams.items()):
        for element in diagram["elements"]:
            if element["kind"] in COVERED_KINDS and (diagram_id, element["id"]) not in covered:
                findings.append(
                    Finding(
                        "UNCOVERED_ELEMENT",
                        element.get("source", diagram["source"]),
                        element.get("line"),
                        f"{element['kind'].capitalize()} {diagram_id}#{element['id']} "
                        f"('{element['label']}') is covered by no requirement; derive at "
                        f"least one {_level(diagram)}-level requirement from it.",
                    )
                )
    return findings


def _level(diagram: dict) -> str:
    return "software" if diagram["type"] == "sequence" else "system"


def _wish_ids(config: ProductConfig) -> set[str]:
    if not config.wishes_file.is_file():
        return set()
    return {
        block.data["id"]
        for block in read_yaml_blocks(config.wishes_file, "wish")
        if isinstance(block.data, dict) and isinstance(block.data.get("id"), str)
    }


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
