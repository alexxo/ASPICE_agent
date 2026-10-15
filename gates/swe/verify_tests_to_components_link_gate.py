"""verify_tests_to_components_link_gate — SWE.5 BP2, BP3, BP5: every component tested on its own.

Every component of role component has a passing component test: a file under
qf.yaml paths.integration_tests_dir naming it as @component[<id>], with at
least one passed result in the integration suite (decisions 2, 4 and 12 of the
integration stage); no @component names a component that does not exist. Every
step of the plan's integration order has a passing test among its selection —
a component tested by @component or a flow by @flow (decision 8).
On a selected run only the components and steps it covers need a passing test
(decision 32 of the unit stages).

    python gates/swe/verify_tests_to_components_link_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_integration_tool import (  # noqa: E402
    integration_steps,
    read_architecture,
    run_integration,
)
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_unit_markers_tool import scan_integration_tests  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402

GATE = "verify_tests_to_components_link_gate"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    if stack is None:
        return []  # check_stack_decision_gate reports a missing or broken stack
    arch = read_architecture(config)
    built = set(arch.components)
    tests = scan_integration_tests(config, stack)
    findings: list[Finding] = []
    for test in tests:
        for component, line in test.components.items():
            if component not in built:
                findings.append(
                    Finding(
                        "UNKNOWN_COMPONENT",
                        test.path,
                        line,
                        f"@component[{component}] names no component of the architecture.",
                    )
                )
    run = run_integration(config, stack, tests)
    passing = run.passing
    tested = {c for t in tests if t.path in passing for c in t.components}
    flows = {f for t in tests if t.path in passing for f in t.flows}
    for component in sorted(c for c in built - tested if run.covers("components", c)):
        file, line = arch.places[component]
        findings.append(
            Finding(
                "MISSING_COMPONENT_TEST",
                file,
                line,
                f"Component {component} has no passing component test marked "
                f"@component[{component}].",
            )
        )
    for step, line in integration_steps(config):
        if not any(run.covers("components", c) for c in step["components"]):
            continue  # a selected run that covers none of the step's components
        if not set(step["selection"]) & (tested | flows):
            findings.append(
                Finding(
                    "UNTESTED_STEP",
                    config.relative(config.verification_plan_file),
                    line,
                    f"Integration step '{step['step']}' has no passing test among its "
                    f"selection ({', '.join(step['selection'])}).",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
