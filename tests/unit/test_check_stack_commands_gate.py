"""gates/swe/check_stack_commands_gate.py — pinned tools, clean checks, results, coverage."""

import copy

from product_builder import (
    PLAN,
    build_python_product,
    python_stack,
    write_all_code,
    write_all_tests_and_stubs,
)

from gates.swe.check_stack_commands_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _built(tmp_path, stack=None, plan=PLAN):
    root = build_python_product(tmp_path, stack=stack, plan=plan)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    return root


def test_gate_name_follows_the_convention():
    assert GATE == "check_stack_commands_gate"


def test_pinned_tools_clean_checks_and_enough_coverage_pass(tmp_path):
    assert _rules(_built(tmp_path)) == []


def test_a_tool_reporting_another_version_is_reported(tmp_path):
    stack = python_stack()
    stack["checks"]["lint"]["version"] = "0.0.1"
    assert _rules(_built(tmp_path, stack)) == ["TOOL_VERSION_MISMATCH"]


def test_a_failing_check_is_reported(tmp_path):
    root = _built(tmp_path)
    (root / "src" / "web_app" / "signin_form.py").write_text(
        "# @unit[signin-form]\nimport os\n\n\ndef run(value):\n    return value + 1\n"
    )
    assert _rules(root) == ["COMMAND_FAILED"]  # ruff: os imported but unused


def test_a_suite_writing_no_results_is_reported(tmp_path):
    stack = python_stack()
    stack["suites"]["unit"]["results"] = "elsewhere/unit.xml"
    assert _rules(_built(tmp_path, stack)) == ["MISSING_RESULTS"]


def test_a_suite_that_crashes_without_results_is_reported_twice(tmp_path):
    stack = python_stack()
    stack["suites"]["unit"]["run"] = "exit 3"
    assert _rules(_built(tmp_path, stack)) == [
        "COMMAND_FAILED",
        "MISSING_COVERAGE",
        "MISSING_RESULTS",
    ]


def test_a_suite_writing_no_coverage_is_reported(tmp_path):
    stack = python_stack()
    stack["suites"]["unit"]["coverage"] = "elsewhere/coverage.xml"
    assert _rules(_built(tmp_path, stack)) == ["MISSING_COVERAGE"]


def test_coverage_below_the_plans_minimum_is_reported(tmp_path):
    plan = copy.deepcopy(PLAN)
    plan["unit"]["coverage"]["minimum"] = 100
    root = _built(tmp_path, plan=plan)
    path = root / "src" / "web_app" / "signin_form.py"
    path.write_text(path.read_text() + "\n\ndef unused():\n    return 1\n")
    assert _rules(root) == ["COVERAGE_BELOW_MINIMUM"]


def test_failing_tests_are_not_this_gates_to_report(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)  # stubs: every test fails, results are written
    assert _rules(root) == []
