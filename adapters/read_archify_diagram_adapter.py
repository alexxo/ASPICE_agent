"""Read an Archify diagram and its invariants into the element list of diagram.v1.

Archify (tt-a1i/archify) writes one JSON spec per diagram and renders HTML from
it. This adapter is the framework's tracer: it copies every element of that spec
onto the framework's form, so no gate ever reads Archify's own format.

    Archify type    nodes from      edges from     edge kind
    architecture    components      connections    edge
    sequence        participants    messages       message
    workflow        nodes           edges          edge
    dataflow        nodes           flows          edge
    lifecycle       states          transitions    edge

The rules a diagram cannot express live in <diagram>.invariants.yaml next to it
(invariants.v1) and are merged as elements of kind invariant.

The adapter only translates. An element it cannot translate faithfully — no ID,
no label, an endpoint missing, an ID used twice — is reported as a problem and
left out, never invented. Problems use the findings shape (rule, file, line,
message), so check_diagram_contract_gate passes them on unchanged.

Run as a command:  read_archify_diagram_adapter.py <diagram.json> [--root DIR]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

__all__ = ["AdapterResult", "diagram_type", "read_archify_diagram", "read_archify_diagrams"]

# Archify diagram_type -> (node collection, edge collection, edge kind)
COLLECTIONS: dict[str, tuple[str, str, str]] = {
    "architecture": ("components", "connections", "edge"),
    "sequence": ("participants", "messages", "message"),
    "workflow": ("nodes", "edges", "edge"),
    "dataflow": ("nodes", "flows", "edge"),
    "lifecycle": ("states", "transitions", "edge"),
}
DIAGRAM_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass(frozen=True)
class AdapterResult:
    """diagram is a diagram.v1 document, or None when nothing could be read."""

    diagram: dict[str, Any] | None
    problems: list[Finding] = field(default_factory=list)


def read_archify_diagram(path: Path, root: Path) -> AdapterResult:
    """Translate one Archify spec, plus its invariants file if present."""
    path, root = Path(path), Path(root)
    source = _relative(path, root)
    diagram_id = path.name.split(".", 1)[0]
    if not DIAGRAM_ID.match(diagram_id):
        return _failed(
            "INVALID_DIAGRAM_ID",
            source,
            f"Diagram ID '{diagram_id}' (the file name up to its first dot) must be "
            "lower-case words joined by hyphens, e.g. auth-flow.architecture.json.",
        )

    text = path.read_text(encoding="utf-8")
    try:
        spec = json.loads(text)
    except json.JSONDecodeError as err:
        return _failed("UNREADABLE_DIAGRAM", source, f"Not valid JSON: {err.msg}.", line=err.lineno)
    diagram_type = spec.get("diagram_type") if isinstance(spec, dict) else None
    if diagram_type not in COLLECTIONS:
        return _failed(
            "UNSUPPORTED_DIAGRAM_TYPE",
            source,
            f"diagram_type '{diagram_type}' is not one the adapter reads: "
            f"{', '.join(COLLECTIONS)}.",
        )

    lines = _item_lines(text)
    nodes_key, edges_key, edge_kind = COLLECTIONS[diagram_type]
    elements: list[dict[str, Any]] = []
    problems: list[Finding] = []

    for index, item in enumerate(spec.get(nodes_key) or []):
        line = lines.get((nodes_key, index))
        if _complete(item, ("id", "label"), nodes_key, index, source, line, problems):
            elements.append(_element(item["id"], "node", item["label"], line))

    for index, item in enumerate(spec.get(edges_key) or []):
        line = lines.get((edges_key, index))
        required = ("id", "label", "from", "to")
        if _complete(item, required, edges_key, index, source, line, problems):
            edge = _element(item["id"], edge_kind, item["label"], line)
            edge.update({"from": item["from"], "to": item["to"]})
            elements.append(edge)

    elements.extend(_invariants(path, root, diagram_id, problems))
    elements = _without_duplicates(elements, source, problems)

    if not elements:
        problems.append(
            Finding("EMPTY_DIAGRAM", source, None, "The diagram has no element to read.")
        )
        return AdapterResult(None, problems)

    diagram = {"diagram": diagram_id, "type": diagram_type, "source": source, "elements": elements}
    violations = validate(diagram, "diagram")
    if violations:  # a translation bug, not a product problem
        first = violations[0]
        raise RuntimeError(f"adapter output breaks diagram.v1 at '{first.path}': {first.message}")
    return AdapterResult(diagram, problems)


def read_archify_diagrams(directory: Path, root: Path) -> list[tuple[Path, AdapterResult]]:
    """Every Archify spec (*.json) in a directory, in file-name order."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return [(path, read_archify_diagram(path, root)) for path in sorted(directory.glob("*.json"))]


def diagram_type(path: Path, result: AdapterResult) -> str | None:
    """The diagram's type as read, else as its file name declares it (<id>.<type>.json)."""
    if result.diagram is not None:
        return result.diagram["type"]
    parts = Path(path).name.split(".")
    return parts[1] if len(parts) == 3 and parts[1] in COLLECTIONS else None


def _element(element_id: str, kind: str, label: str, line: int | None) -> dict[str, Any]:
    element: dict[str, Any] = {"id": element_id, "kind": kind, "label": label}
    if line:
        element["line"] = line
    return element


def _complete(item, required, collection, index, source, line, problems) -> bool:
    """True when the item has every field; otherwise one problem per missing field."""
    if not isinstance(item, dict):
        problems.append(
            Finding("UNREADABLE_DIAGRAM", source, line, f"{collection}[{index}] is not an object.")
        )
        return False
    rules = {"id": "MISSING_ID", "label": "MISSING_LABEL", "from": "MISSING_ENDPOINT"}
    rules["to"] = "MISSING_ENDPOINT"
    name = item.get("id") or f"{collection}[{index}]"
    missing = [key for key in required if not item.get(key)]
    for key in missing:
        problems.append(
            Finding(
                rules[key],
                source,
                line,
                f"{name} has no '{key}'; every element needs an id, a label and, for a "
                "connection, both endpoints, so requirements can point at it.",
            )
        )
    return not missing


def _invariants(path: Path, root: Path, diagram_id: str, problems: list[Finding]) -> list[dict]:
    file = path.with_name(f"{diagram_id}.invariants.yaml")
    if not file.is_file():
        return []
    source = _relative(file, root)
    try:
        data = read_yaml_file(file)
    except YamlReadError as err:
        problems.append(Finding("INVALID_INVARIANTS", source, err.line, err.message))
        return []
    violations = validate(data, "invariants")
    if violations:
        first = violations[0]
        problems.append(
            Finding(
                "INVALID_INVARIANTS",
                source,
                None,
                f"Breaks invariants.v1 at '{first.path or 'the file'}': {first.message}.",
            )
        )
        return []
    if data["diagram"] != diagram_id:
        problems.append(
            Finding(
                "INVARIANTS_FOR_OTHER_DIAGRAM",
                source,
                None,
                f"The file names diagram '{data['diagram']}' but sits next to '{diagram_id}'.",
            )
        )
        return []
    lines = _item_lines(file.read_text(encoding="utf-8"))
    result = []
    for index, entry in enumerate(data["invariants"]):
        element = _element(entry["id"], "invariant", entry["statement"], None)
        element["source"] = source
        line = lines.get(("invariants", index))
        if line:
            element["line"] = line
        result.append(element)
    return result


def _without_duplicates(elements, source, problems) -> list[dict]:
    seen: set[str] = set()
    kept = []
    for element in elements:
        if element["id"] in seen:
            problems.append(
                Finding(
                    "DUPLICATE_ID",
                    element.get("source", source),
                    element.get("line"),
                    f"ID '{element['id']}' is used by more than one element of the diagram; "
                    "a requirement pointing at it would be ambiguous.",
                )
            )
            continue
        seen.add(element["id"])
        kept.append(element)
    return kept


def _item_lines(text: str) -> dict[tuple[str, int], int]:
    """(collection, index) -> 1-based line of each item of each top-level list.

    The line of an item's "id" when it has one, otherwise the line its object
    starts on. JSON is read through YAML here only for positions; the data
    itself comes from json/yaml loaders.
    """
    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return {}
    lines: dict[tuple[str, int], int] = {}
    if not isinstance(root, yaml.MappingNode):
        return lines
    for key, value in root.value:
        if not isinstance(value, yaml.SequenceNode):
            continue
        for index, item in enumerate(value.value):
            mark = item.start_mark
            if isinstance(item, yaml.MappingNode):
                for item_key, item_value in item.value:
                    if item_key.value == "id":
                        mark = item_value.start_mark
            lines[(str(key.value), index)] = mark.line + 1
    return lines


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _failed(rule: str, source: str, message: str, line: int | None = None) -> AdapterResult:
    return AdapterResult(None, [Finding(rule, source, line, message)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("diagram", type=Path, help="the Archify JSON spec")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="product root")
    args = parser.parse_args(argv)
    result = read_archify_diagram(args.diagram, args.root)
    for p in result.problems:
        print(f"{p.file}:{p.line or ''}: {p.rule} {p.message}", file=sys.stderr)
    if result.diagram is not None:
        print(json.dumps(result.diagram, indent=2, ensure_ascii=False))
    return 1 if result.problems else 0


if __name__ == "__main__":
    sys.exit(main())
