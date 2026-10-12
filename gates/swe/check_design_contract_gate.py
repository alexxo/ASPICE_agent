"""check_design_contract_gate — SWE.2 BP1–BP4: architecture follows diagram and requirements.

The ```yaml component and ```yaml interface blocks under paths.architecture_dir
follow their contracts; every node of an architecture diagram is one component
and every edge one interface; every participant of a sequence diagram is a
component; interfaces connect components that exist and are external exactly
when one end is; every mode transition names a mode of its component; every
software requirement is met by a component; and components name only
requirements and decisions that exist.

    python gates/swe/check_design_contract_gate.py [--root PRODUCT]
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
from tools.validate_contract_tool import validate  # noqa: E402

GATE = "check_design_contract_gate"
TAGS = ("component", "interface")


def check(config: ProductConfig) -> list[Finding]:
    folder = config.architecture_dir
    files = sorted(folder.glob("*.md")) if folder.is_dir() else []
    findings: list[Finding] = []
    records: dict[str, list] = {tag: [] for tag in TAGS}
    for path in files:
        shown = config.relative(path)
        for tag in TAGS:
            for block in read_yaml_blocks(path, tag):
                if block.error:
                    findings.append(Finding("UNREADABLE_BLOCK", shown, block.line, block.error))
                    continue
                if not isinstance(block.data, dict):
                    findings.append(
                        Finding(
                            "UNREADABLE_BLOCK",
                            shown,
                            block.line,
                            f"A {tag} block must be a mapping.",
                        )
                    )
                    continue
                violations = validate(block.data, tag)
                if violations:
                    first = violations[0]
                    line = block.key_lines.get(first.path.split("/")[0], block.line)
                    name = block.data.get("id", f"A {tag}")
                    findings.append(
                        Finding(
                            "SCHEMA_VIOLATION",
                            shown,
                            line,
                            f"{name}: '{first.path or 'the block'}' {first.message} ({tag}.v1).",
                        )
                    )
                # the cross checks use every readable block, so one broken field is one
                # finding — not also an uncovered node and unmet requirements
                records[tag].append((shown, block))
    if not any(records.values()) and not findings:
        return [
            Finding(
                "NO_ARCHITECTURE",
                config.relative(folder),
                None,
                "No component or interface found; the architecture belongs here.",
            )
        ]
    findings += _ids(records)
    findings += _diagrams(config, records)
    findings += _participants(config)
    findings += _interfaces(records)
    findings += _modes(records)
    findings += _requirements(config, records)
    findings += _decisions(config, records)
    return findings


def _ids(records) -> list[Finding]:
    seen, findings = set(), []
    for tag in TAGS:
        for shown, block in records[tag]:
            cid = block.data.get("id")
            if cid in seen:
                findings.append(
                    Finding("DUPLICATE_ID", shown, block.line, f"ID '{cid}' is used twice.")
                )
            seen.add(cid)
    return findings


def _diagrams(config, records) -> list[Finding]:
    nodes, edges = set(), set()
    for _path, result in read_archify_diagrams(config.diagrams_dir, config.root):
        diagram = result.diagram
        if diagram is None or diagram["type"] != "architecture":
            continue
        for element in diagram["elements"]:
            ref = f"{diagram['diagram']}#{element['id']}"
            if element["kind"] == "node":
                nodes.add(ref)
            elif element["kind"] == "edge":
                edges.add(ref)
    findings, used = [], set()
    for tag, wanted, kind in (("component", nodes, "node"), ("interface", edges, "edge")):
        for shown, block in records[tag]:
            ref = block.data.get("derived_from")
            used.add(ref)
            if isinstance(ref, str) and ref not in wanted:
                findings.append(
                    Finding(
                        "UNKNOWN_ELEMENT",
                        shown,
                        block.key_lines.get("derived_from"),
                        f"{tag.capitalize()} {block.data.get('id')} derives from {ref}, "
                        f"which is no "
                        f"{kind} of an architecture diagram.",
                    )
                )
    folder = config.relative(config.architecture_dir)
    for ref in sorted(nodes - used):
        findings.append(
            Finding(
                "UNCOVERED_NODE", folder, None, f"Node {ref} is no component of the architecture."
            )
        )
    for ref in sorted(edges - used):
        findings.append(
            Finding(
                "UNCOVERED_EDGE", folder, None, f"Edge {ref} is no interface of the architecture."
            )
        )
    return findings


def _participants(config) -> list[Finding]:
    """A participant must be a node of an architecture diagram; UNCOVERED_NODE
    already makes every such node a component, so a missing component is one
    finding, not two."""
    diagrams = [
        (path, r.diagram)
        for path, r in read_archify_diagrams(config.diagrams_dir, config.root)
        if r.diagram is not None
    ]
    nodes = {
        e["id"]
        for _path, d in diagrams
        if d["type"] == "architecture"
        for e in d["elements"]
        if e["kind"] == "node"
    }
    findings = []
    for path, diagram in diagrams:
        if diagram["type"] != "sequence":
            continue
        for element in diagram["elements"]:
            if element["kind"] == "node" and element["id"] not in nodes:
                findings.append(
                    Finding(
                        "UNKNOWN_PARTICIPANT",
                        config.relative(path),
                        element.get("line"),
                        f"Participant {diagram['diagram']}#{element['id']} is no node of an "
                        "architecture diagram, so no component.",
                    )
                )
    return findings


def _modes(records) -> list[Finding]:
    findings = []
    for shown, block in records["component"]:
        modes = block.data.get("modes")
        if not isinstance(modes, list) or not all(isinstance(m, dict) for m in modes):
            continue  # not applicable, or the schema finding covers it
        known = {m.get("mode") for m in modes}
        for mode in modes:
            for target in mode.get("to") or []:
                if target not in known:
                    findings.append(
                        Finding(
                            "UNKNOWN_MODE",
                            shown,
                            block.key_lines.get("modes"),
                            f"Component {block.data.get('id')} moves from {mode.get('mode')} "
                            f"to '{target}', which is none of its modes.",
                        )
                    )
    return findings


def _interfaces(records) -> list[Finding]:
    roles = {b.data.get("id"): b.data.get("role") for _shown, b in records["component"]}
    findings = []
    for shown, block in records["interface"]:
        data = block.data
        if not all(isinstance(data.get(k), str | bool) for k in ("id", "from", "to", "external")):
            continue  # the schema finding covers it
        missing = [end for end in ("from", "to") if data[end] not in roles]
        for end in missing:
            findings.append(
                Finding(
                    "UNKNOWN_COMPONENT",
                    shown,
                    block.key_lines.get(end),
                    f"Interface {data['id']} goes {end} '{data[end]}', which is no component.",
                )
            )
        if missing:
            continue
        external = "external" in (roles[data["from"]], roles[data["to"]])
        if data["external"] != external:
            ends = "one end is" if external else "no end is"
            findings.append(
                Finding(
                    "EXTERNAL_MISMATCH",
                    shown,
                    block.key_lines.get("external"),
                    f"Interface {data['id']} is marked external: {str(data['external']).lower()}, "
                    f"but {ends} external.",
                )
            )
    return findings


def _requirements(config, records) -> list[Finding]:
    reqs = {r.text("uid"): r for r in read_requirements(config) if r.text("uid")}
    met, findings = set(), []
    for shown, block in records["component"]:
        for uid in block.data.get("meets") or []:
            if uid in reqs:
                met.add(uid)
            else:
                findings.append(
                    Finding(
                        "UNKNOWN_REQUIREMENT",
                        shown,
                        block.key_lines.get("meets"),
                        f"Component {block.data.get('id')} meets {uid}, which does not exist.",
                    )
                )
    for uid, req in sorted(reqs.items()):
        if req.text("level") == "software" and uid not in met:
            findings.append(
                Finding(
                    "UNMET_REQUIREMENT",
                    req.file,
                    req.line("uid"),
                    f"{uid} is met by no component of the architecture.",
                )
            )
    return findings


def _decisions(config, records) -> list[Finding]:
    folder = config.decisions_dir
    known = set()
    for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        known.update(re.findall(r"^id: (ADR-[0-9]{4})\s*$", path.read_text(), re.M))
    findings = []
    for shown, block in records["component"]:
        for adr in block.data.get("decisions") or []:
            if adr not in known:
                findings.append(
                    Finding(
                        "UNKNOWN_DECISION",
                        shown,
                        block.key_lines.get("decisions"),
                        f"Component {block.data.get('id')} names {adr}, "
                        "which has no decision record.",
                    )
                )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
