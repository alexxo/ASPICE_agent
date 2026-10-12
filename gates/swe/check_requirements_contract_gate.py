"""check_requirements_contract_gate — SWE.1 BP1–BP5: the requirement contract.

Checks every requirement block of the product against requirement.v1, and the
rules across blocks no schema can express: unique UIDs, a one-level refines tree
(software → system), every system requirement refined, a happy case in every
requirement and an edge or error case in every high-criticality one, and an
observability requirement for every feature (every sequence diagram).

The cross checks use every readable block, valid or not, so one broken field is
reported once and does not make its parent look unrefined as well.

    python gates/swe/check_requirements_contract_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.read_archify_diagram_adapter import read_archify_diagrams  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_requirements_tool import RequirementBlock, read_requirements  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

GATE = "check_requirements_contract_gate"


def check(config: ProductConfig) -> list[Finding]:
    blocks = read_requirements(config)
    if not blocks:
        return [
            Finding(
                "NO_REQUIREMENTS",
                config.relative(config.requirements_dir),
                None,
                "No ```yaml requirement block found; the requirements derived from the "
                "approved diagrams belong here.",
            )
        ]
    findings: list[Finding] = []
    readable: list[RequirementBlock] = []
    for req in blocks:
        if req.block.error:
            findings.append(
                Finding(
                    "UNREADABLE_REQUIREMENT",
                    req.file,
                    req.block.line,
                    f"The block cannot be read: {req.block.error}.",
                )
            )
            continue
        readable.append(req)
        findings.extend(_schema(req))
    first = _unique(readable, findings)
    findings.extend(_tree(readable, first))
    findings.extend(_cases(readable))
    findings.extend(_observability(config, readable))
    return findings


def _schema(req: RequirementBlock) -> list[Finding]:
    name = req.text("uid") or "The requirement"
    return [
        Finding(
            "SCHEMA_VIOLATION",
            req.file,
            req.line(v.path.split("/")[0]) if v.path else req.block.line,
            f"{name}: '{v.path or 'the block'}' {v.message} (requirement.v1).",
        )
        for v in validate(req.block.data, "requirement")
    ]


def _unique(readable, findings) -> dict[str, RequirementBlock]:
    """The first block of every UID; later ones are DUPLICATE_UID."""
    first: dict[str, RequirementBlock] = {}
    for req in readable:
        uid = req.text("uid")
        if uid is None:
            continue
        if uid in first:
            seen = first[uid]
            findings.append(
                Finding(
                    "DUPLICATE_UID",
                    req.file,
                    req.line("uid"),
                    f"{uid} is already used at {seen.file}:{seen.line('uid')}; give this "
                    "requirement the next free number.",
                )
            )
        else:
            first[uid] = req
    return first


def _tree(readable, first) -> list[Finding]:
    findings = []
    refined: set[str] = set()
    for req in readable:
        parent_uid = req.text("refines")
        if req.text("level") != "software" or parent_uid is None:
            continue
        parent = first.get(parent_uid)
        if parent is None:
            findings.append(
                Finding(
                    "UNKNOWN_PARENT",
                    req.file,
                    req.line("refines"),
                    f"{req.text('uid')} refines {parent_uid}, which does not exist.",
                )
            )
        elif parent.text("level") != "system":
            findings.append(
                Finding(
                    "PARENT_NOT_SYSTEM",
                    req.file,
                    req.line("refines"),
                    f"{req.text('uid')} refines {parent_uid}, a software-level requirement; "
                    "a software requirement refines a system-level one.",
                )
            )
        else:
            refined.add(parent_uid)
    for uid, req in first.items():
        if req.text("level") == "system" and uid not in refined:
            findings.append(
                Finding(
                    "UNREFINED_SYSTEM_REQUIREMENT",
                    req.file,
                    req.line("uid"),
                    f"{uid} is refined by no software-level requirement; derive at least one "
                    "from the feature's sequence diagram.",
                )
            )
    return findings


def _cases(readable) -> list[Finding]:
    """Every requirement has a happy case; a high-criticality one also an edge or error case.

    Edge and error cases are what an LLM leaves out first, so they are checked,
    not hoped for. A criterion without a case is the schema's finding, not this one.
    """
    findings = []
    for req in readable:
        criteria = req.data.get("acceptance_criteria")
        if not isinstance(criteria, list):
            continue
        cases = {c.get("case") for c in criteria if isinstance(c, dict)}
        uid = req.text("uid") or "The requirement"
        if "happy" not in cases:
            findings.append(
                Finding(
                    "MISSING_HAPPY_CASE",
                    req.file,
                    req.line("acceptance_criteria"),
                    f"{uid} has no criterion of case happy; state the intended behaviour.",
                )
            )
        if req.text("criticality") == "high" and not cases & {"edge", "error"}:
            findings.append(
                Finding(
                    "MISSING_ERROR_CASE",
                    req.file,
                    req.line("acceptance_criteria"),
                    f"{uid} is of high criticality but has no criterion of case edge or error; "
                    "state how it behaves at a boundary or when something fails.",
                )
            )
    return findings


def _observability(config, readable) -> list[Finding]:
    observed = {
        req.text("derived_from").split("#", 1)[0]
        for req in readable
        if req.text("kind") == "observability" and "#" in (req.text("derived_from") or "")
    }
    findings = []
    for _path, result in read_archify_diagrams(config.diagrams_dir, config.root):
        diagram = result.diagram
        if diagram is None or diagram["type"] != "sequence" or diagram["diagram"] in observed:
            continue
        findings.append(
            Finding(
                "MISSING_OBSERVABILITY",
                diagram["source"],
                None,
                f"Feature '{diagram['diagram']}' has no requirement of kind observability; "
                "derive one from its diagram, stating the events it logs and what watches it.",
            )
        )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
