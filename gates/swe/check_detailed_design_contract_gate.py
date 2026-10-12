"""check_detailed_design_contract_gate — SWE.3 BP1/BP2/BP4: each component's detailed design.

Per component of the architecture, under paths.detailed_design_dir: its
<component>.md holds ```yaml unit blocks that follow unit.v1, with IDs unique in
the product; every unit comes from a node of the component's structure diagram
<component>.architecture.json and every node is a unit; calls name units of the
same component and are the structure diagram's edges, both ways; ranges are not
upside down; and once a unit calls another, <component>.sequence.json shows every
call as a message, has only units as participants, and no message that is
neither a call nor the reply to one. The environment variables declared with the
design (qf.yaml paths.env_variables_file, when it exists) follow env_variable.v1,
each name once.

    python gates/swe/check_detailed_design_contract_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.read_archify_diagram_adapter import read_archify_diagrams  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

GATE = "check_detailed_design_contract_gate"


def check(config: ProductConfig) -> list[Finding]:
    folder = config.detailed_design_dir
    files = sorted(folder.glob("*.md")) if folder.is_dir() else []
    if not files:
        return [
            Finding(
                "NO_DETAILED_DESIGN",
                config.relative(folder),
                None,
                "No detailed design found; one <component>.md per component belongs here.",
            )
        ]
    components = _components(config)
    findings: list[Finding] = []
    designs = {path.stem: path for path in files}
    for cid in sorted(components - designs.keys()):
        findings.append(
            Finding(
                "MISSING_DETAILED_DESIGN",
                config.relative(folder),
                None,
                f"Component {cid} has no detailed design ({cid}.md).",
            )
        )
    diagrams, problems = _diagrams(config)
    findings += problems
    units: dict[str, list] = {}
    for cid, path in sorted(designs.items()):
        shown = config.relative(path)
        if cid not in components:
            findings.append(
                Finding(
                    "UNKNOWN_COMPONENT",
                    shown,
                    None,
                    f"{path.name} is the design of '{cid}', which is no component "
                    "of the architecture.",
                )
            )
            continue
        units[cid], block_findings = _units(path, shown)
        findings += block_findings
    findings += _unique_ids(units)
    for cid, blocks in sorted(units.items()):
        findings += _component(config, cid, blocks, diagrams)
    return findings + _env_variables(config)


def _env_variables(config: ProductConfig) -> list[Finding]:
    """The environment variables declared with the design: each record follows
    env_variable.v1, and each name is declared once. The file is optional — a
    product whose code reads no variable has none."""
    path = config.env_variables_file
    if not path.is_file():
        return []
    shown = config.relative(path)
    findings: list[Finding] = []
    seen: dict[str, int] = {}
    for block in read_yaml_blocks(path, "env_variable"):
        if block.error or not isinstance(block.data, dict):
            message = block.error or "An env_variable block must be a mapping."
            findings.append(Finding("UNREADABLE_BLOCK", shown, block.line, message))
            continue
        violations = validate(block.data, "env_variable")
        if violations:
            first = violations[0]
            findings.append(
                Finding(
                    "SCHEMA_VIOLATION",
                    shown,
                    block.key_lines.get(first.path.split("/")[0], block.line),
                    f"{block.data.get('name', 'A variable')}: '{first.path or 'the block'}' "
                    f"{first.message} (env_variable.v1).",
                )
            )
        name = block.data.get("name")
        if isinstance(name, str):
            if name in seen:
                findings.append(
                    Finding(
                        "DUPLICATE_VARIABLE",
                        shown,
                        block.line,
                        f"{name} is declared twice (first at line {seen[name]}).",
                    )
                )
            seen.setdefault(name, block.line)
    return findings


def _components(config) -> set[str]:
    """The IDs of the architecture's components of role component."""
    folder = config.architecture_dir
    ids = set()
    for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        for block in read_yaml_blocks(path, "component"):
            data = block.data
            if not block.error and isinstance(data, dict) and data.get("role") == "component":
                ids.add(data.get("id"))
    return ids


def _diagrams(config):
    """(component ID, type) -> diagram.v1, and the adapter's problems as findings."""
    diagrams, problems = {}, []
    for _path, result in read_archify_diagrams(config.detailed_design_dir, config.root):
        problems += result.problems
        if result.diagram is not None:
            diagrams[(result.diagram["diagram"], result.diagram["type"])] = result.diagram
    return diagrams, problems


def _units(path, shown):
    """The readable unit blocks of one design file, and their findings."""
    kept, findings = [], []
    for block in read_yaml_blocks(path, "unit"):
        if block.error:
            findings.append(Finding("UNREADABLE_BLOCK", shown, block.line, block.error))
            continue
        if not isinstance(block.data, dict):
            findings.append(
                Finding("UNREADABLE_BLOCK", shown, block.line, "A unit block must be a mapping.")
            )
            continue
        violations = validate(block.data, "unit")
        if violations:
            first = violations[0]
            line = block.key_lines.get(first.path.split("/")[0], block.line)
            findings.append(
                Finding(
                    "SCHEMA_VIOLATION",
                    shown,
                    line,
                    f"{block.data.get('id', 'A unit')}: '{first.path or 'the block'}' "
                    f"{first.message} (unit.v1).",
                )
            )
        # cross checks use every readable block: one broken field, one finding
        kept.append((shown, block))
    return kept, findings


def _unique_ids(units) -> list[Finding]:
    seen, findings = set(), []
    for _cid, blocks in sorted(units.items()):
        for shown, block in blocks:
            uid = block.data.get("id")
            if uid in seen:
                findings.append(
                    Finding(
                        "DUPLICATE_ID",
                        shown,
                        block.line,
                        f"Unit ID '{uid}' is used twice; code names a unit as @unit[{uid}], "
                        "so an ID is unique in the product.",
                    )
                )
            seen.add(uid)
    return findings


def _component(config, cid, blocks, diagrams) -> list[Finding]:
    folder = config.relative(config.detailed_design_dir)
    findings: list[Finding] = []
    structure = diagrams.get((cid, "architecture"))
    if structure is None:
        return [
            Finding(
                "MISSING_DESIGN_DIAGRAM",
                folder,
                None,
                f"Component {cid} has no structure diagram ({cid}.architecture.json).",
            )
        ]
    nodes = _nodes(structure)
    node_of: dict[str, str] = {}
    used = set()
    for shown, block in blocks:
        ref = block.data.get("derived_from")
        if not isinstance(ref, str):
            continue
        diagram, _, node = ref.partition("#")
        if diagram != cid or node not in nodes:
            findings.append(
                Finding(
                    "UNKNOWN_ELEMENT",
                    shown,
                    block.key_lines.get("derived_from"),
                    f"Unit {block.data.get('id')} derives from {ref}, which is no node of "
                    f"{cid}.architecture.json.",
                )
            )
            continue
        node_of[block.data.get("id")] = node
        used.add(node)
    for node in sorted(nodes - used):
        findings.append(
            Finding(
                "UNCOVERED_NODE",
                structure["source"],
                None,
                f"Node {cid}#{node} is no unit of the detailed design.",
            )
        )
    findings += _dangling(structure, nodes)
    findings += _ranges(blocks)
    calls, call_findings = _calls(cid, blocks, node_of)
    findings += call_findings
    findings += _against(
        structure,
        calls,
        missing=("UNDRAWN_CALL", "is drawn as no edge of"),
        extra=("UNDECLARED_EDGE", "edge", "is no declared call"),
        replies=False,
    )
    sequence = diagrams.get((cid, "sequence"))
    if sequence is None:
        if calls:
            findings.append(
                Finding(
                    "MISSING_DESIGN_DIAGRAM",
                    folder,
                    None,
                    f"Units of {cid} call each other, but there is no sequence diagram "
                    f"({cid}.sequence.json).",
                )
            )
        return findings
    participants = _nodes(sequence)
    for node in sorted(participants - set(node_of.values())):
        findings.append(
            Finding(
                "UNKNOWN_PARTICIPANT",
                sequence["source"],
                None,
                f"Participant {cid}#{node} is no unit of {cid}.",
            )
        )
    findings += _dangling(sequence, participants)
    findings += _against(
        sequence,
        calls,
        missing=("UNSHOWN_CALL", "is shown as no message of"),
        extra=("UNDECLARED_CALL", "message", "is neither a declared call nor the reply to one"),
        replies=True,
    )
    return findings


def _nodes(diagram) -> set[str]:
    return {e["id"] for e in diagram["elements"] if e["kind"] == "node"}


def _links(diagram) -> list[dict]:
    return [e for e in diagram["elements"] if e["kind"] in ("edge", "message")]


def _dangling(diagram, nodes) -> list[Finding]:
    findings = []
    for link in _links(diagram):
        for end in ("from", "to"):
            if link[end] not in nodes:
                findings.append(
                    Finding(
                        "DANGLING_ENDPOINT",
                        diagram["source"],
                        link.get("line"),
                        f"{link['id']} goes {end} '{link[end]}', which is no node of the diagram.",
                    )
                )
    return findings


def _ranges(blocks) -> list[Finding]:
    findings = []
    for shown, block in blocks:
        for side in ("inputs", "outputs"):
            for port in block.data.get(side) or []:
                rng = port.get("range") if isinstance(port, dict) else None
                if not isinstance(rng, dict):
                    continue
                low, high = rng.get("min"), rng.get("max")
                if isinstance(low, int | float) and isinstance(high, int | float) and low > high:
                    findings.append(
                        Finding(
                            "INVALID_RANGE",
                            shown,
                            block.key_lines.get(side),
                            f"Unit {block.data.get('id')}: {port.get('name')} has range "
                            f"{low} to {high}; the minimum is above the maximum.",
                        )
                    )
    return findings


def _calls(cid, blocks, node_of):
    """The component's calls as (caller node, called node), and UNKNOWN_UNIT."""
    calls, findings = set(), []
    for shown, block in blocks:
        caller = node_of.get(block.data.get("id"))
        for target in block.data.get("calls") or []:
            if target not in node_of:
                findings.append(
                    Finding(
                        "UNKNOWN_UNIT",
                        shown,
                        block.key_lines.get("calls"),
                        f"Unit {block.data.get('id')} calls '{target}', which is no unit of {cid}.",
                    )
                )
            elif caller is not None:
                calls.add((caller, node_of[target]))
    return calls, findings


def _against(diagram, calls, missing, extra, replies) -> list[Finding]:
    """The diagram's links and the declared calls agree, both ways."""
    nodes = _nodes(diagram)
    links = {(e["from"], e["to"]): e for e in _links(diagram) if {e["from"], e["to"]} <= nodes}
    findings = []
    rule, says = missing
    for a, b in sorted(calls - links.keys()):
        findings.append(
            Finding(rule, diagram["source"], None, f"The call {a} → {b} {says} the diagram.")
        )
    rule, kind, says = extra
    for (a, b), link in sorted(links.items()):
        if (a, b) in calls or (replies and (b, a) in calls):
            continue
        findings.append(
            Finding(rule, diagram["source"], link.get("line"), f"The {kind} {a} → {b} {says}.")
        )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
