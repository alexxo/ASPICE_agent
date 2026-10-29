"""verify_decision_records_gate — SWE.2 BP3: every decision record well-formed and consistent.

Each file in paths.decisions_dir holds one ```yaml decision block following
decision.v1; its file name starts with the number of its ID; IDs are unique; the
choice is one of the options; and a superseded record exists.

A record that says who decides (decided_by) has what its card on the decisions
page needs (INCOMPLETE_DECISION): the requirements it serves, and — the
person's — the question and why they are asked, then once accepted who
answered; — the agent's — why it is not critical and where it is in the work.
Each requirement it names exists (UNKNOWN_REQUIREMENT), and the agent decides
none that is critical (AGENT_DECIDED_CRITICAL: criticality high, or kind
security — that one is the person's). Once a record says who decides, the
decisions page (agent/render_decisions_tool.py) exists (MISSING_DECISIONS_PAGE)
and is what the records render now (DECISIONS_PAGE_OUTDATED).

    python gates/swe/verify_decision_records_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.render_decisions_tool import decisions_page_findings  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_requirements_tool import critical, read_requirements  # noqa: E402
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

GATE = "verify_decision_records_gate"


def check(config: ProductConfig) -> list[Finding]:
    folder = config.decisions_dir
    findings: list[Finding] = []
    records = []
    for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        shown = config.relative(path)
        blocks = read_yaml_blocks(path, "decision")
        if len(blocks) != 1 or blocks[0].error:
            reason = blocks[0].error if blocks and blocks[0].error else f"found {len(blocks)}"
            findings.append(
                Finding(
                    "UNREADABLE_DECISION",
                    shown,
                    None,
                    f"A decision record holds exactly one readable decision block ({reason}).",
                )
            )
            continue
        block = blocks[0]
        violations = validate(block.data, "decision")
        if violations:
            first = violations[0]
            line = block.key_lines.get(first.path.split("/")[0], block.line)
            findings.append(
                Finding(
                    "SCHEMA_VIOLATION",
                    shown,
                    line,
                    f"'{first.path or 'the block'}' {first.message} (decision.v1).",
                )
            )
            continue
        records.append((path, shown, block))
    seen: dict[str, str] = {}
    for path, shown, block in records:
        data = block.data
        number = data["id"].removeprefix("ADR-")
        if not path.name.startswith(f"{number}-"):
            findings.append(
                Finding(
                    "FILE_NAME_MISMATCH",
                    shown,
                    block.key_lines.get("id"),
                    f"{data['id']} belongs in a file named {number}-<slug>.md.",
                )
            )
        if data["id"] in seen:
            findings.append(
                Finding(
                    "DUPLICATE_DECISION",
                    shown,
                    block.key_lines.get("id"),
                    f"{data['id']} is already used in {seen[data['id']]}.",
                )
            )
        seen.setdefault(data["id"], shown)
        if data["choice"] not in {option["name"] for option in data["options"]}:
            findings.append(
                Finding(
                    "CHOICE_NOT_AN_OPTION",
                    shown,
                    block.key_lines.get("choice"),
                    f"{data['id']} chooses '{data['choice']}', which is none of its options.",
                )
            )
    for _path, shown, block in records:
        old = block.data.get("supersedes")
        if old and old not in seen:
            findings.append(
                Finding(
                    "UNKNOWN_SUPERSEDED",
                    shown,
                    block.key_lines.get("supersedes"),
                    f"{block.data['id']} supersedes {old}, which does not exist.",
                )
            )
    findings += _who_decides(config, records)
    return findings


# What each decider's card needs, beyond requirements: the person's while proposed,
# once accepted; the agent's.
NEEDS = {
    ("person", "proposed"): ["question", "why_you", "proposed_because"],
    ("person", "accepted"): ["question", "why_you", "answered_by"],
    ("person", "superseded"): ["question", "why_you"],
    ("agent", "proposed"): ["not_critical", "where"],
    ("agent", "accepted"): ["not_critical", "where"],
    ("agent", "superseded"): ["not_critical", "where"],
}


def _who_decides(config: ProductConfig, records: list) -> list[Finding]:
    """The rules of a record that says who decides, and the decisions page."""
    decided = [(shown, block) for _path, shown, block in records if "decided_by" in block.data]
    if not decided:
        return []
    requirements = {r.text("uid"): r.data for r in read_requirements(config) if r.text("uid")}
    findings: list[Finding] = []
    for shown, block in decided:
        data = block.data
        who = data["decided_by"]
        missing = [
            name for name in ["requirements", *NEEDS[(who, data["status"])]] if name not in data
        ]
        if missing:
            findings.append(
                Finding(
                    "INCOMPLETE_DECISION",
                    shown,
                    block.key_lines.get("decided_by"),
                    f"{data['id']}, decided by the {who} ({data['status']}), lacks "
                    f"{', '.join(missing)}: its card on the decisions page needs them.",
                )
            )
        for uid in data.get("requirements", []):
            if uid not in requirements:
                findings.append(
                    Finding(
                        "UNKNOWN_REQUIREMENT",
                        shown,
                        block.key_lines.get("requirements"),
                        f"{data['id']} serves {uid}, which is no requirement of the product.",
                    )
                )
            elif who == "agent" and critical(requirements[uid]):
                findings.append(
                    Finding(
                        "AGENT_DECIDED_CRITICAL",
                        shown,
                        block.key_lines.get("decided_by"),
                        f"{data['id']} is decided by the agent, but {uid} is critical "
                        "(criticality high, or kind security): the person decides it — "
                        "decided_by person, a question and a proposal.",
                    )
                )
    return findings + decisions_page_findings(config)


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
