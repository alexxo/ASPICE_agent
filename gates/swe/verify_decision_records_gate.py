"""verify_decision_records_gate — SWE.2 BP3: every decision record well-formed and consistent.

Each file in paths.decisions_dir holds one ```yaml decision block following
decision.v1; its file name starts with the number of its ID; IDs are unique; the
choice is one of the options; and a superseded record exists.

    python gates/swe/verify_decision_records_gate.py [--root PRODUCT]
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
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
