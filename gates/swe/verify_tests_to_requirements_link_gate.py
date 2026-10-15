"""verify_tests_to_requirements_link_gate — SWE.4 BP2–BP4: every unit tested, every test passing.

The unit suite's JUnit XML results (the shared run of decision 13) are tied to
their test files (decision 11): a result that matches no test file is
reported; every test passes; and every unit of the detailed design has at least
one passing test in a test file that names it with @unit. Through the units,
the tests reach the requirements their components meet.
On a selected run only the units it covers need a passing test (decision 32).

    python gates/swe/verify_tests_to_requirements_link_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_test_results_tool import ResultsError, map_to_file, read_results  # noqa: E402
from tools.read_unit_markers_tool import design_units, scan_sources  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack, run_command  # noqa: E402

GATE = "verify_tests_to_requirements_link_gate"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    units = design_units(config)
    if stack is None or not units:
        return []  # the stack and detailed design gates report what is missing
    tests = {s.path: s for s in scan_sources(config, stack) if s.kind == "test"}
    run = run_command(config, "suites", "unit", stack["suites"]["unit"])
    shown = config.relative(config.stack_file)
    findings: list[Finding] = []
    try:
        results = read_results(run.result_paths)
    except ResultsError as err:
        results = []
        findings.append(Finding("UNMAPPED_RESULT", shown, None, f"suites.unit results: {err}."))
    tested: set[str] = set()
    for result in results:
        file = map_to_file(result, list(tests))
        if file is None:
            findings.append(
                Finding(
                    "UNMAPPED_RESULT",
                    shown,
                    None,
                    f"The result of {result.label} matches no test file; the runner must "
                    "write a file attribute or a path-like classname.",
                )
            )
            continue
        if result.outcome in ("failed", "error"):
            findings.append(Finding("FAILED_TEST", file, None, f"{result.label} {result.outcome}."))
        elif result.outcome == "passed":
            tested.update(tests[file].units)
    for unit, (component, design) in sorted(units.items()):
        if unit not in tested and run.covers("units", unit):
            findings.append(
                Finding(
                    "UNTESTED_UNIT",
                    design,
                    None,
                    f"Unit {unit} of {component} has no passing unit test.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
