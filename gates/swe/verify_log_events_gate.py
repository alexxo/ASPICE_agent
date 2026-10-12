"""verify_log_events_gate — principle #22, SWE.5 BP4: every log event asserted by a passing test.

For every requirement of kind observability, each event its events list names
appears literally in a component or integration test that carries the
requirement's @sdoc[<REQ-UID>] marker and has at least one passed result in the
integration suite (decision 9 of the integration stage). That the test really
captures the emitted events, with their three fields, is the reviewer's.

    python gates/swe/verify_log_events_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_integration_tool import run_integration  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_requirements_tool import read_requirements  # noqa: E402
from tools.read_unit_markers_tool import scan_integration_tests  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

GATE = "verify_log_events_gate"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    if stack is None:
        return []  # check_stack_decision_gate reports a missing or broken stack
    observed = [
        req
        for req in read_requirements(config)
        if req.data.get("kind") == "observability" and not validate(req.data, "requirement")
    ]
    if not observed:
        return []
    tests = scan_integration_tests(config, stack)
    passing = run_integration(config, stack, tests).passing
    findings: list[Finding] = []
    for req in observed:
        uid = req.data["uid"]
        asserting = [t for t in tests if t.path in passing and uid in t.requirements]
        for event in req.data["events"]:
            if not any(event in t.text for t in asserting):
                findings.append(
                    Finding(
                        "UNTESTED_EVENT",
                        req.file,
                        req.line("events"),
                        f"Event {event} of {uid} is named by no passing integration test "
                        f"marked @sdoc[{uid}].",
                    )
                )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
