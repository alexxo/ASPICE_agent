"""verify_software_tests_to_requirements_link_gate — SWE.6 BP1–BP4: every requirement tested.

Every requirement that is neither a constraint nor measured has a passing
software-level test — a file under qf.yaml paths.software_tests_dir matching
the stack's software_test_files — that names it as @sdoc[<REQ-UID>]: in the
e2e suite for level system, in the software suite for level software
(decisions 3 and 4 of the software verification stage). No marker names a
requirement that does not exist; a suite that is needed writes its results, and
every software-level test in them passes. Measured requirements are
verify_nfr_thresholds_gate's.
On a selected run only the requirements it covers need a passing test (decision
32 of the unit stages).

    python gates/swe/verify_software_tests_to_requirements_link_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_integration_tool import run_suite  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_requirements_tool import read_requirements  # noqa: E402
from tools.read_software_tool import proof, valid_requirements  # noqa: E402
from tools.read_unit_markers_tool import scan_software_tests  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402

GATE = "verify_software_tests_to_requirements_link_gate"
LEVEL = {"e2e": "system", "software": "software"}


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    if stack is None:
        return []  # check_stack_decision_gate reports a missing or broken stack
    known = {r.data.get("uid") for r in read_requirements(config)}
    tests = scan_software_tests(config, stack)
    findings: list[Finding] = []
    for test in tests:
        for uid, line in test.requirements.items():
            if uid not in known:
                findings.append(
                    Finding(
                        "UNKNOWN_REQUIREMENT",
                        test.path,
                        line,
                        f"@sdoc[{uid}] names no requirement.",
                    )
                )
    needed = [(r, proof(r.data)) for r in valid_requirements(config)]
    needed = [(r, suite) for r, suite in needed if suite in LEVEL]
    passing: dict[str, set[str]] = {}
    runs = {}
    failed: set[tuple[str, str]] = set()
    for suite in sorted({suite for _, suite in needed}):
        if not tests:
            continue  # nothing to run: every requirement below is unverified
        run = run_suite(config, stack, suite, tests)
        if run.results is None:
            findings.append(
                Finding(
                    "MISSING_RESULTS",
                    config.relative(config.stack_file),
                    None,
                    f"The {suite} suite is not declared or wrote no readable JUnit XML "
                    f"results, so no {LEVEL[suite]}-level requirement can be shown verified.",
                )
            )
            continue
        passing[suite] = run.passing
        runs[suite] = run
        for file, results in sorted(run.by_file.items()):
            for result in results:
                if result.outcome in ("failed", "error") and (file, result.label) not in failed:
                    failed.add((file, result.label))
                    findings.append(
                        Finding(
                            "FAILED_TEST",
                            file,
                            None,
                            f"{result.label} {result.outcome} in the {suite} suite; "
                            "change the code, never the test.",
                        )
                    )
    for req, suite in needed:
        uid = req.data["uid"]
        if suite in runs and not runs[suite].covers("requirements", uid):
            continue  # a selected run that does not cover this requirement
        if not any(t.path in passing.get(suite, ()) and uid in t.requirements for t in tests):
            findings.append(
                Finding(
                    "UNVERIFIED_REQUIREMENT",
                    req.file,
                    req.line("uid"),
                    f"{LEVEL[suite].capitalize()}-level requirement {uid} has no passing "
                    f"test marked @sdoc[{uid}] in the {suite} suite.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
