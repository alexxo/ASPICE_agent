"""verify_nfr_thresholds_gate — SWE.6 BP3: every measured value meets its threshold.

Every requirement with a measurement_method has a value measured by the suite
its instrument names, written to the measurements path of that suite's stack
entry (measurements.v1) and in the unit its threshold writes (MISSING_MEASUREMENT);
every such value meets the threshold (THRESHOLD_NOT_MET). A measurements file
that is not measurements.v1 is reported (decision 6 of the software
verification stage).
On a selected run only the requirements it covers need a measured value
(decision 32 of the unit stages).

    python gates/swe/verify_nfr_thresholds_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_software_tool import (  # noqa: E402
    Measurement,
    proof,
    read_measurements,
    read_threshold,
    valid_requirements,
)
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack, run_command  # noqa: E402

GATE = "verify_nfr_thresholds_gate"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    if stack is None:
        return []  # check_stack_decision_gate reports a missing or broken stack
    measured = [r for r in valid_requirements(config) if proof(r.data) == "measurement"]
    if not measured:
        return []
    shown = config.relative(config.stack_file)
    findings: list[Finding] = []
    values: dict[str, list[Measurement]] = {}
    runs = {}
    for suite in sorted({r.data["measurement_method"]["instrument"] for r in measured}):
        entry = stack["suites"].get(suite)
        if entry is None or "measurements" not in entry:
            values[suite] = []  # every requirement it measures is reported below
            continue
        run = run_command(config, "suites", suite, entry)
        runs[suite] = run
        values[suite], problems = read_measurements(run.measurement_paths)
        for name, problem in problems:
            findings.append(
                Finding("SCHEMA_VIOLATION", shown, None, f"{suite} measurements {name}: {problem}.")
            )
    for req in measured:
        uid = req.data["uid"]
        suite = req.data["measurement_method"]["instrument"]
        threshold = read_threshold(req.data["threshold"])
        mine = [m for m in values[suite] if m.requirement == uid and m.unit == threshold.unit]
        if not mine and suite in runs and not runs[suite].covers("requirements", uid):
            continue  # a selected run that does not cover this requirement
        if not mine:
            unit = f" in '{threshold.unit}'" if threshold.unit else ""
            findings.append(
                Finding(
                    "MISSING_MEASUREMENT",
                    req.file,
                    req.line("measurement_method"),
                    f"{uid} has no value{unit} measured by the {suite} suite; its stack entry "
                    "names the measurements file the suite writes.",
                )
            )
        for m in mine:
            if not threshold.met_by(m.value):
                findings.append(
                    Finding(
                        "THRESHOLD_NOT_MET",
                        req.file,
                        req.line("threshold"),
                        f"{uid} measured {m.value:g}"
                        + (f" {m.unit}" if m.unit else "")
                        + f" ({m.file}), threshold {threshold}.",
                    )
                )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
