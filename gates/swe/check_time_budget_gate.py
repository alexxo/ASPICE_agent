"""check_time_budget_gate — SWE.4 BP3, SWE.5 BP5, SWE.6 BP3: the tests are fast by design.

Every suite of the unit, integration and software levels runs every test on
every change (decision 32 of the unit stages), within its level's time budget
(decision 33): the verification plan's time_budget, else the framework's
default — the unit suite 120 seconds and each unit test 0.5 seconds, the
integration suite 300 seconds, the software suite 600 seconds. The defaults
are sized for CI with about twice the headroom a healthy suite needs. A suite
that ran longer, wall clock (SUITE_OVER_BUDGET), and a unit test whose JUnit
result took longer (TEST_OVER_BUDGET), fail: the remedy is the design of the
tests — in parallel, each behaviour once at the lowest level that shows it —
never a looser budget without a reason. A budget looser than the default
states why (MISSING_BUDGET_REASON).

The gate judges the runs kept for the tree (run_stack_commands_tool); it runs
no suite itself, so it judges what the gates before it ran.

    python gates/swe/check_time_budget_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_test_results_tool import ResultsError, read_results  # noqa: E402
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import kept_run, read_stack, tree_key  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

GATE = "check_time_budget_gate"

__all__ = ["DEFAULTS", "budgets", "check"]

# level → its default budget, in seconds
DEFAULTS = {
    "unit": {"suite_seconds": 120, "test_seconds": 0.5},
    "integration": {"suite_seconds": 300},
    "software": {"suite_seconds": 600},
}


def budgets(config: ProductConfig) -> tuple[dict[str, dict], list[Finding]]:
    """Each level's budget — the plan's, else the default — and the plan's budgets
    that are looser than the default without a reason."""
    path = config.verification_plan_file
    shown = config.relative(path)
    blocks = read_yaml_blocks(path, "verification_plan") if path.is_file() else []
    plan, line = {}, None
    readable = len(blocks) == 1 and not blocks[0].error
    if readable and not validate(blocks[0].data, "verification_plan"):
        plan, line = blocks[0].data, blocks[0].line
    chosen: dict[str, dict] = {}
    findings: list[Finding] = []
    for level, default in DEFAULTS.items():
        given = (plan.get(level) or {}).get("time_budget") or {}
        chosen[level] = {**default, **{k: v for k, v in given.items() if k != "reason"}}
        looser = [k for k in default if k in given and given[k] > default[k]]
        if looser and "reason" not in given:
            findings.append(
                Finding(
                    "MISSING_BUDGET_REASON",
                    shown,
                    line,
                    f"The {level} time_budget is looser than the default "
                    f"({', '.join(f'{k} {given[k]} > {default[k]}' for k in looser)}) "
                    "and gives no reason; tighten it, or say why in time_budget.reason.",
                )
            )
    return chosen, findings


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    if stack is None:
        return []  # check_stack_decision_gate reports a missing or broken stack
    chosen, findings = budgets(config)
    shown = config.relative(config.verification_plan_file)
    key = tree_key(config.root)
    for level, budget in chosen.items():
        if level not in stack["suites"]:
            continue
        run = kept_run(config, key, "suites", level)
        if run is None or run.seconds is None:
            continue  # the suite did not run for this tree, or ran nothing
        if run.seconds > budget["suite_seconds"]:
            findings.append(
                Finding(
                    "SUITE_OVER_BUDGET",
                    shown,
                    None,
                    f"suites.{level} ran {run.seconds:.1f} s, over its budget of "
                    f"{budget['suite_seconds']} s: run its tests in parallel and test each "
                    "behaviour once, at the lowest level that shows it.",
                )
            )
        limit = budget.get("test_seconds")
        if limit is None:
            continue
        try:
            results = read_results([Path(p) for p in run.results])
        except ResultsError:
            continue  # the gate that reads the suite's results reports it
        for result in results:
            if result.seconds is not None and result.seconds > limit:
                findings.append(
                    Finding(
                        "TEST_OVER_BUDGET",
                        shown,
                        None,
                        f"{result.label} took {result.seconds:.2f} s, over the {level} test "
                        f"budget of {limit} s: a {level} test needs no slow resource.",
                    )
                )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
