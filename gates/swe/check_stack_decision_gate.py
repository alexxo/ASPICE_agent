"""check_stack_decision_gate — SWE.2: the tech stack is pinned, complete and decided.

The stack file (qf.yaml paths.stack_file) follows stack.v2 with every version
exact, and the decision record it names exists. Every area of AREAS (decision
10 of the architecture stage) has a row: a tool, or not needed with its reason
(MISSING_STACK_AREA, MISSING_REASON) — except the areas the product cannot do
without, which need a tool. The areas
the framework gives name what the framework uses: the host's tools, and the
qf.yaml slot of the diagram and requirements plugins (GIVEN_AREA_MISMATCH).

    python gates/swe/check_stack_decision_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402
from tools.write_stack_table_tool import AREAS, GIVEN, NEEDED  # noqa: E402

GATE = "check_stack_decision_gate"

# The slot that names the tool of a framework-given area, after "slot:" in GIVEN.
SLOT = "slot:"


def check(config: ProductConfig) -> list[Finding]:
    shown = config.relative(config.stack_file)
    if not config.stack_file.is_file():
        return [
            Finding(
                "MISSING_STACK",
                shown,
                None,
                "No tech stack yet; it is the first decision of the architecture.",
            )
        ]
    try:
        stack = read_yaml_file(config.stack_file)
    except YamlReadError as err:
        return [Finding("INVALID_STACK", shown, err.line, err.message)]
    violations = validate(stack, "stack")
    if violations:
        first = violations[0]
        return [
            Finding(
                "INVALID_STACK",
                shown,
                None,
                f"Breaks stack.v2 at '{first.path or 'the file'}': {first.message}.",
            )
        ]
    findings = []
    if not (config.root / stack["decision_record"]).is_file():
        findings.append(
            Finding(
                "MISSING_DECISION_RECORD",
                shown,
                None,
                f"The decision record {stack['decision_record']} does not exist.",
            )
        )
    return findings + _areas(config, stack["areas"], shown)


def _areas(config: ProductConfig, rows: list[dict], shown: str) -> list[Finding]:
    findings = []
    for area in AREAS:
        mine = [row for row in rows if row["area"] == area]
        tools = [row["tool"] for row in mine if "tool" in row]
        if not mine:
            findings.append(
                Finding(
                    "MISSING_STACK_AREA",
                    shown,
                    None,
                    f"The stack has no row for area '{area}'; name its tool, or mark it "
                    "not_needed with the reason.",
                )
            )
        elif area in NEEDED and not tools:
            findings.append(
                Finding(
                    "MISSING_STACK_AREA",
                    shown,
                    None,
                    f"Area '{area}' is marked not needed, but the gates run its tool; name it.",
                )
            )
        given = GIVEN.get(area, "")
        if given.startswith(SLOT):
            given = config.slots.get(given[len(SLOT) :], "")
        if mine and given and not any(_same(tool, given) for tool in tools):
            findings.append(
                Finding(
                    "GIVEN_AREA_MISMATCH",
                    shown,
                    None,
                    f"Area '{area}' is given by the framework: its tool is '{given}'; "
                    + (
                        f"the stack names {', '.join(repr(t) for t in tools)}."
                        if tools
                        else "the stack marks it not needed."
                    ),
                )
            )
    findings += [
        Finding(
            "MISSING_REASON",
            shown,
            None,
            f"Area '{row['area']}' is marked not needed without a reason; say why.",
        )
        for row in rows
        if "not_needed" in row and not row["not_needed"].strip()
    ]
    return findings


def _same(tool: str, given: str) -> bool:
    """Equal but for case, spaces and punctuation: 'GitHub Actions' is 'github-actions'."""
    return re.sub(r"[^a-z0-9]", "", tool.lower()) == re.sub(r"[^a-z0-9]", "", given.lower())


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
