"""check_stack_commands_gate — SWE.3 BP3, SWE.4 BP2: the declared checks and unit suite run clean.

Every check of the stack (lint, format, static analysis) runs with the command
its stack row declares, and the unit suite with the command of the verification
plan, each after its tool's version_command, whose output must contain the
version the stack pins (decision 12). A check passes with exit code 0. The unit
suite writes its JUnit XML results and its Cobertura XML coverage where the plan
says; a failing test is verify_tests_to_requirements_link_gate's to
report. The coverage over the whole report reaches the verification plan's
minimum, in its metric (decision 16). The other suites run with their stages.
Each command runs once per tree (decision 13).
A selected run that selected no test runs nothing and is not short of results,
and coverage is judged on full runs only (decision 32).

    python gates/swe/check_stack_commands_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_coverage_tool import CoverageError, read_coverage  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import CommandRun, read_stack, run_command  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

GATE = "check_stack_commands_gate"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    if stack is None:
        return []  # check_stack_decision_gate reports a missing or broken stack
    shown = config.relative(config.stack_file)
    findings: list[Finding] = []
    for name, entry in stack["checks"].items():
        run = run_command(config, "checks", name, entry)
        findings += _version(shown, f"checks.{name}", entry, run)
        if run.exit_code != 0:
            findings.append(
                Finding(
                    "COMMAND_FAILED",
                    shown,
                    None,
                    f"checks.{name} ({entry['run']}) exited {run.exit_code}: {_tail(run.output)}",
                )
            )
    entry = stack["suites"].get("unit")
    if entry is None:
        return findings  # check_verification_plan_gate reports a plan without its unit suite
    run = run_command(config, "suites", "unit", entry)
    findings += _version(shown, "suites.unit", entry, run)
    shown = config.relative(config.verification_plan_file)  # the suite's own findings
    if run.ran_nothing:
        return findings  # no unit test is traced to the change, so none ran
    if not run.results:
        if run.exit_code != 0:
            findings.append(
                Finding(
                    "COMMAND_FAILED",
                    shown,
                    None,
                    f"suites.unit exited {run.exit_code} without results: {_tail(run.output)}",
                )
            )
        findings.append(
            Finding(
                "MISSING_RESULTS",
                shown,
                None,
                f"suites.unit wrote no JUnit XML at {entry['results']}.",
            )
        )
    if run.full:  # coverage is measured on a full run only (decision 32)
        findings += _coverage(config, shown, entry, run)
    return findings


def _version(shown: str, label: str, entry: dict, run: CommandRun) -> list[Finding]:
    if run.version_exit == 0 and entry["version"].lstrip("v") in run.version_output:
        return []
    return [
        Finding(
            "TOOL_VERSION_MISMATCH",
            shown,
            None,
            f"{label}: '{entry['version_command']}' does not report {entry['tool']} "
            f"{entry['version']}; it said: {_tail(run.version_output)}",
        )
    ]


def _coverage(config: ProductConfig, shown: str, entry: dict, run: CommandRun) -> list[Finding]:
    if not run.coverage:
        return [
            Finding(
                "MISSING_COVERAGE",
                shown,
                None,
                f"suites.unit wrote no Cobertura XML at {entry['coverage']}.",
            )
        ]
    plan = _plan(config)
    if plan is None:
        return []  # check_verification_plan_gate reports a missing or broken plan
    metric = plan["unit"]["coverage"]["metric"]
    minimum = plan["unit"]["coverage"]["minimum"]
    try:
        measured = read_coverage(Path(run.coverage)).get(metric)
    except CoverageError as err:
        return [Finding("MISSING_COVERAGE", shown, None, f"suites.unit coverage: {err}.")]
    if measured is None or measured < minimum:
        return [
            Finding(
                "COVERAGE_BELOW_MINIMUM",
                config.relative(config.verification_plan_file),
                None,
                f"The unit tests cover {measured if measured is not None else 'no'} % of "
                f"{metric}; the plan asks at least {minimum} %.",
            )
        ]
    return []


def _plan(config: ProductConfig) -> dict | None:
    path = config.verification_plan_file
    blocks = read_yaml_blocks(path, "verification_plan") if path.is_file() else []
    if len(blocks) != 1 or blocks[0].error or validate(blocks[0].data, "verification_plan"):
        return None
    return blocks[0].data


def _tail(output: str) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    return lines[-1][:200] if lines else "no output"


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
