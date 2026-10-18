"""gates/swe/check_time_budget_gate.py — every suite and unit test within its time budget."""

import copy
import json
from dataclasses import asdict

import pytest
from product_builder import PLAN, build_python_product

from gates.swe.check_time_budget_gate import DEFAULTS, GATE, check
from tools.read_product_config_tool import read_product_config
from tools.run_stack_commands_tool import RUNS_DIR, CommandRun, tree_key


def _plan(**budgets) -> dict:
    plan = copy.deepcopy(PLAN)
    for level, budget in budgets.items():
        plan[level]["time_budget"] = budget
    return plan


def _kept(root, suite, seconds, cases=()):
    """A suite run kept for the tree, as run_stack_commands_tool keeps it."""
    store = root / RUNS_DIR / tree_key(root)
    store.mkdir(parents=True, exist_ok=True)
    results = store / f"{suite}.xml"
    rows = "".join(f'<testcase classname="t" name="{n}" time="{s}"/>' for n, s in cases)
    results.write_text(f"<testsuite>{rows}</testsuite>")
    run = CommandRun("suites", suite, 0, "", 0, "", results=[str(results)], seconds=seconds)
    (store / f"suites-{suite}.json").write_text(json.dumps(asdict(run)))


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


@pytest.fixture
def product(tmp_path):
    return build_python_product(tmp_path, branch=None)


def test_gate_name_follows_the_convention():
    assert GATE == "check_time_budget_gate"


def test_the_defaults_are_those_of_the_design():
    assert DEFAULTS == {
        "unit": {"suite_seconds": 120, "test_seconds": 0.5},
        "integration": {"suite_seconds": 300},
        "software": {"suite_seconds": 600},
    }


def test_runs_within_the_default_budgets_pass(product):
    _kept(product, "unit", 30.0, [("test_a", 0.01), ("test_b", 0.4)])
    _kept(product, "integration", 250.0)
    assert _rules(product) == []


def test_without_a_run_there_is_nothing_to_judge(product):
    assert _rules(product) == []


def test_a_suite_over_its_default_budget_fails(product):
    _kept(product, "unit", 121.0)
    _kept(product, "software", 601.0)
    assert _rules(product) == ["SUITE_OVER_BUDGET", "SUITE_OVER_BUDGET"]


def test_a_unit_test_over_its_budget_fails(product):
    _kept(product, "unit", 10.0, [("test_fast", 0.1), ("test_slow", 0.9)])
    (finding,) = check(read_product_config(product))
    assert finding.rule == "TEST_OVER_BUDGET"
    assert "t.test_slow took 0.90 s" in finding.message


def test_the_plan_tightens_a_budget(tmp_path):
    root = build_python_product(tmp_path, plan=_plan(unit={"suite_seconds": 20}), branch=None)
    _kept(root, "unit", 21.0)
    assert _rules(root) == ["SUITE_OVER_BUDGET"]


def test_a_looser_budget_needs_its_reason(tmp_path):
    looser = {"suite_seconds": 400, "test_seconds": 1}
    root = build_python_product(tmp_path, plan=_plan(unit=looser), branch=None)
    _kept(root, "unit", 300.0, [("test_db", 0.8)])
    assert _rules(root) == ["MISSING_BUDGET_REASON"]


def test_a_looser_budget_with_its_reason_holds(tmp_path):
    reason = {"suite_seconds": 400, "reason": "the bridge's load tables are large"}
    root = build_python_product(tmp_path, plan=_plan(unit=reason), branch=None)
    _kept(root, "unit", 300.0)
    assert _rules(root) == []
