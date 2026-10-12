"""check_stack_decision_gate — SWE.2: the tech stack exists, is pinned, and has its decision.

The stack file (qf.yaml paths.stack_file) follows stack.v1 with every version
exact, the decision record it names exists, and every verification suite a
requirement names as its instrument has a command in the stack — so every
threshold can actually be measured.

    python gates/swe/check_stack_decision_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_requirements_tool import read_requirements  # noqa: E402
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

GATE = "check_stack_decision_gate"


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
                f"Breaks stack.v1 at '{first.path or 'the file'}': {first.message}.",
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
    suites = set(stack["suites"])
    for req in read_requirements(config):
        method = req.data.get("measurement_method")
        suite = method.get("instrument") if isinstance(method, dict) else None
        if isinstance(suite, str) and suite not in suites:
            findings.append(
                Finding(
                    "UNKNOWN_INSTRUMENT",
                    req.file,
                    req.line("measurement_method"),
                    f"{req.text('uid')} is measured by suite '{suite}', which the stack gives no "
                    "command; add it to the stack's suites.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
