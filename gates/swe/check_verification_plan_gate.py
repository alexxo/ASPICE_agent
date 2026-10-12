"""check_verification_plan_gate — SWE.4 BP1/BP2: the verification plan exists and is complete.

The file qf.yaml paths.verification_plan_file holds exactly one ```yaml
verification_plan block that follows verification_plan.v1: the unit section's
techniques, pass/fail, entry and exit criteria, infrastructure, selection,
regression and minimum coverage. Once the product has component or
integration tests (stage 7), the integration section too, whose order names
existing components and every component of role component (decision 7 of the
integration stage). Once it has software-level tests (stage 8), the software
section too (decision 7 of the software verification stage). Once it has a
validation scenario (stage 11), the validation section too
(MISSING_VALIDATION_SECTION), listing every scenario (UNSELECTED_SCENARIO) and
none that does not exist (UNKNOWN_SCENARIO).

    python gates/swe/check_verification_plan_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_integration_tool import read_architecture  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_unit_markers_tool import (  # noqa: E402
    scan_integration_tests,
    scan_software_tests,
)
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402
from tools.write_validation_record_tool import scan_scenarios  # noqa: E402

GATE = "check_verification_plan_gate"


def check(config: ProductConfig) -> list[Finding]:
    path = config.verification_plan_file
    shown = config.relative(path)
    if not path.is_file():
        return [
            Finding(
                "MISSING_VERIFICATION_PLAN",
                shown,
                None,
                "No verification plan; the tester writes its unit section before the first test.",
            )
        ]
    blocks = read_yaml_blocks(path, "verification_plan")
    if not blocks:
        return [
            Finding(
                "MISSING_VERIFICATION_PLAN",
                shown,
                None,
                "The file holds no ```yaml verification_plan block.",
            )
        ]
    if len(blocks) > 1:
        return [
            Finding(
                "MULTIPLE_PLANS",
                shown,
                blocks[1].line,
                f"The file holds {len(blocks)} verification_plan blocks; one plan, one block.",
            )
        ]
    block = blocks[0]
    if block.error:
        return [Finding("UNREADABLE_BLOCK", shown, block.line, block.error)]
    violations = validate(block.data, "verification_plan")
    if violations:
        first = violations[0]
        return [
            Finding(
                "SCHEMA_VIOLATION",
                shown,
                block.line,
                f"Breaks verification_plan.v1 at '{first.path or 'the block'}': {first.message}.",
            )
        ]
    return [*_integration(config, block), *_software(config, block), *_validation(config, block)]


def _validation(config: ProductConfig, block) -> list[Finding]:
    shown = config.relative(config.verification_plan_file)
    scenarios = scan_scenarios(config, read_stack(config))
    if "validation" not in block.data:
        if not scenarios:
            return []  # the village crew writes it with the first scenario
        return [
            Finding(
                "MISSING_VALIDATION_SECTION",
                shown,
                block.line,
                "The product has validation scenarios, but the plan has no validation "
                "section; the village crew writes it with them.",
            )
        ]
    line = block.key_lines.get("validation", block.line)
    listed = [e["scenario"] for e in block.data["validation"]["scenarios"]]
    known = {s.path for s in scenarios}
    findings = [
        Finding(
            "UNKNOWN_SCENARIO",
            shown,
            line,
            f"The validation section lists {path}, which is no scenario: no such file, or "
            "it names no wish.",
        )
        for path in listed
        if path not in known
    ]
    findings += [
        Finding(
            "UNSELECTED_SCENARIO",
            s.path,
            None,
            f"Scenario {s.path} is not in the plan's validation section; list it with its "
            "technique, criteria, entry criteria and environment.",
        )
        for s in scenarios
        if s.path not in listed
    ]
    return findings


def _software(config: ProductConfig, block) -> list[Finding]:
    if "software" in block.data:
        return []
    stack = read_stack(config)
    if stack is None or not scan_software_tests(config, stack):
        return []  # the bridge tester writes it with the first software-level test
    return [
        Finding(
            "MISSING_SOFTWARE_SECTION",
            config.relative(config.verification_plan_file),
            block.line,
            "The product has software-level tests, but the plan has no software section; "
            "the bridge tester writes it with them.",
        )
    ]


def _integration(config: ProductConfig, block) -> list[Finding]:
    shown = config.relative(config.verification_plan_file)
    plan = block.data
    if "integration" not in plan:
        stack = read_stack(config)
        if stack is None or not scan_integration_tests(config, stack):
            return []  # the assembler writes it with the first integration test
        return [
            Finding(
                "MISSING_INTEGRATION_SECTION",
                shown,
                block.line,
                "The product has component or integration tests, but the plan has no "
                "integration section; the assembler writes it with them.",
            )
        ]
    built = read_architecture(config).components
    line = block.key_lines.get("integration", block.line)
    findings = []
    scheduled: set[str] = set()
    for step in plan["integration"]["order"]:
        for component in step["components"]:
            scheduled.add(component)
            if component not in built:
                findings.append(
                    Finding(
                        "UNKNOWN_COMPONENT",
                        shown,
                        line,
                        f"Step '{step['step']}' integrates {component}, which is no "
                        "component of the architecture.",
                    )
                )
    for component in built:
        if component not in scheduled:
            findings.append(
                Finding(
                    "UNSCHEDULED_COMPONENT",
                    shown,
                    line,
                    f"Component {component} is integrated in no step of the order.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
