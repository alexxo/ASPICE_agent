"""verify_tests_to_flows_link_gate — SWE.5 BP1, BP4, BP6: the components joined along every flow.

Every approved sequence diagram under qf.yaml paths.diagrams_dir has a passing
integration test naming it as @flow[<id>]; no @flow names one that does not
exist (decisions 4 and 6 of the integration stage). Every interface between
two components of role component is crossed, in either direction, by a message
of a tested flow (decision 5). The integration suite writes its results, and
every component and integration test in them passes (decision 12).
On a selected run only the flows and interfaces it covers need a passing test
(decision 32 of the unit stages).

    python gates/swe/verify_tests_to_flows_link_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_integration_tool import (  # noqa: E402
    read_architecture,
    read_flows,
    run_integration,
)
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_unit_markers_tool import scan_integration_tests  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402

GATE = "verify_tests_to_flows_link_gate"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    if stack is None:
        return []  # check_stack_decision_gate reports a missing or broken stack
    flows = read_flows(config)
    tests = scan_integration_tests(config, stack)
    findings: list[Finding] = []
    for test in tests:
        for flow, line in test.flows.items():
            if flow not in flows:
                findings.append(
                    Finding(
                        "UNKNOWN_FLOW",
                        test.path,
                        line,
                        f"@flow[{flow}] names no approved sequence diagram.",
                    )
                )
    run = run_integration(config, stack, tests)
    if run.results is None:
        findings.append(
            Finding(
                "MISSING_RESULTS",
                config.relative(config.stack_file),
                None,
                "The integration suite wrote no readable JUnit XML results, so no "
                "component or integration test can be shown to pass.",
            )
        )
    for file, results in sorted(run.by_file.items()):
        for result in results:
            if result.outcome in ("failed", "error"):
                findings.append(
                    Finding(
                        "FAILED_INTEGRATION_TEST",
                        file,
                        None,
                        f"{result.label} {result.outcome}; change the code, never the test.",
                    )
                )
    tested = {f for t in tests if t.path in run.passing for f in t.flows if f in flows}
    for flow in sorted(f for f in set(flows) - tested if run.covers("flows", f)):
        findings.append(
            Finding(
                "MISSING_FLOW_TEST",
                flows[flow][0],
                None,
                f"Flow {flow} has no passing integration test marked @flow[{flow}].",
            )
        )
    crossed = set().union(*(flows[f][1] for f in tested)) if tested else set()
    for interface in read_architecture(config).internal_interfaces():
        ends = (interface["from"], interface["to"])
        if not all(run.covers("components", end) for end in ends):
            continue  # a selected run that covers neither end
        if frozenset(ends) not in crossed:
            findings.append(
                Finding(
                    "UNTESTED_INTERFACE",
                    interface["file"],
                    interface["line"],
                    f"Interface {interface['id']} ({interface['from']} → {interface['to']}) "
                    "is crossed by no message of a tested flow.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
