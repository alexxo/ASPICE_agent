"""verify_diagram_to_wishes_link_gate — SWE.2 (drawn first): every wish realised by a diagram.

Each diagram has its <diagram>.wishes.yaml (diagram_wishes.v1), linking elements
to the wishes they realise. The gate checks that every link names an element of
its diagram and a wish that exists, and that every wish of kind behaviour is
realised by at least one element; a wish of kind constraint need not be — it
becomes a constraint requirement at SWE.1. A behaviour wish is also realised by
an element of a sequence diagram, so every feature reaches the software level;
while there is no sequence diagram, check_diagram_contract_gate reports it
instead. Elements of a diagram the adapter
cannot read are not checked here; check_diagram_contract_gate reports it.

    python gates/swe/verify_diagram_to_wishes_link_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.read_archify_diagram_adapter import (  # noqa: E402
    diagram_type,
    read_archify_diagrams,
)
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_yaml_blocks_tool import (  # noqa: E402
    YamlReadError,
    read_yaml_blocks,
    read_yaml_file,
)
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

GATE = "verify_diagram_to_wishes_link_gate"


def check(config: ProductConfig) -> list[Finding]:
    findings: list[Finding] = []
    wishes = _wishes(config)
    wishes_file = config.relative(config.wishes_file)
    if not wishes:
        findings.append(
            Finding(
                "NO_WISHES",
                wishes_file,
                None,
                "No wish found; the diagrams are drawn from the customer's wishes.",
            )
        )
    realised: set[str] = set()
    in_sequence: set[str] = set()
    has_sequence = False
    for path, result in read_archify_diagrams(config.diagrams_dir, config.root):
        diagram_id = path.name.split(".", 1)[0]
        readable = result.diagram is not None and not result.problems
        elements = {e["id"] for e in result.diagram["elements"]} if readable else None
        linked: set[str] = set()
        findings.extend(_links(config, path, diagram_id, elements, wishes, linked))
        realised |= linked
        if diagram_type(path, result) == "sequence":
            has_sequence = True
            in_sequence |= linked
    for wish_id, (kind, line) in sorted(wishes.items()):
        if kind == "constraint":
            continue
        if wish_id not in realised:
            findings.append(
                Finding(
                    "UNCOVERED_WISH",
                    wishes_file,
                    line,
                    f"Wish {wish_id} is realised by no diagram element; draw it, link it in the "
                    "diagram's wishes file, or mark it kind constraint if no diagram can show it.",
                )
            )
        elif has_sequence and wish_id not in in_sequence:
            findings.append(
                Finding(
                    "WISH_NOT_IN_SEQUENCE",
                    wishes_file,
                    line,
                    f"Wish {wish_id} is realised by no element of a sequence diagram; draw its "
                    "steps in its feature's sequence diagram and link them in that diagram's "
                    "wishes file.",
                )
            )
    return findings


def _wishes(config: ProductConfig) -> dict[str, tuple[str, int]]:
    """Wish ID -> (kind, line), from the readable wish blocks."""
    if not config.wishes_file.is_file():
        return {}
    wishes = {}
    for block in read_yaml_blocks(config.wishes_file, "wish"):
        if isinstance(block.data, dict) and isinstance(block.data.get("id"), str):
            wishes[block.data["id"]] = (block.data.get("kind", "behaviour"), block.line)
    return wishes


def _links(config, path, diagram_id, elements, wishes, realised) -> list[Finding]:
    file = path.with_name(f"{diagram_id}.wishes.yaml")
    shown = config.relative(file)
    if not file.is_file():
        return [
            Finding(
                "MISSING_WISH_LINKS",
                config.relative(path),
                None,
                f"Diagram '{diagram_id}' has no {file.name} linking its elements to the "
                "wishes they realise.",
            )
        ]
    try:
        data = read_yaml_file(file)
    except YamlReadError as err:
        return [Finding("INVALID_WISH_LINKS", shown, err.line, err.message)]
    violations = validate(data, "diagram_wishes")
    if violations:
        first = violations[0]
        return [
            Finding(
                "INVALID_WISH_LINKS",
                shown,
                None,
                f"Breaks diagram_wishes.v1 at '{first.path or 'the file'}': {first.message}.",
            )
        ]
    if data["diagram"] != diagram_id:
        return [
            Finding(
                "INVALID_WISH_LINKS",
                shown,
                None,
                f"The file names diagram '{data['diagram']}' but sits next to '{diagram_id}'.",
            )
        ]
    findings = []
    for element, linked in data["links"].items():
        if elements is not None and element not in elements:
            findings.append(
                Finding(
                    "UNKNOWN_ELEMENT",
                    shown,
                    None,
                    f"'{element}' is not an element of diagram '{diagram_id}'.",
                )
            )
            continue
        for wish_id in linked:
            if wish_id not in wishes:
                findings.append(
                    Finding(
                        "UNKNOWN_WISH",
                        shown,
                        None,
                        f"{element} realises {wish_id}, which is not in the " "wishes file.",
                    )
                )
            else:
                realised.add(wish_id)
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
