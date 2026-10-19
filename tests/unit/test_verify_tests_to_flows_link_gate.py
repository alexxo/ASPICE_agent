"""gates/swe/verify_tests_to_flows_link_gate.py — the components joined along every flow."""

from product_builder import (
    FLOW_TEST,
    build_python_product,
    component_test_path,
    edit_plan,
    write_all_code,
    write_all_integration_tests,
    write_all_tests_and_stubs,
    write_events_code,
    write_flow_test,
)

from gates.swe.verify_tests_to_flows_link_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def _rules(root):
    return sorted(f.rule for f in _findings(root))


def _assembled(tmp_path, stack=None):
    root = build_python_product(tmp_path, stack=stack)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    write_events_code(root)
    write_all_integration_tests(root)
    return root


def test_gate_name_follows_the_convention():
    assert GATE == "verify_tests_to_flows_link_gate"


def test_tested_flows_and_passing_tests_pass(tmp_path):
    assert _rules(_assembled(tmp_path)) == []


def test_without_integration_tests_flows_and_interfaces_are_untested(tmp_path):
    findings = _findings(build_python_product(tmp_path))
    assert sorted(f.rule for f in findings) == ["MISSING_FLOW_TEST", "UNTESTED_INTERFACE"]
    flow = next(f for f in findings if f.rule == "MISSING_FLOW_TEST")
    assert flow.file == "docs/diagrams/login.sequence.json"


def test_a_failing_integration_test_is_reported_and_its_flow_untested(tmp_path):
    root = _assembled(tmp_path)
    write_all_code(root)  # the coder's events are gone: the flow test fails
    assert _rules(root) == [
        "FAILED_INTEGRATION_TEST",
        "FAILED_INTEGRATION_TEST",
        "MISSING_FLOW_TEST",
        "UNTESTED_INTERFACE",
    ]


def test_one_failing_result_is_reported_even_when_its_file_passes(tmp_path):
    root = _assembled(tmp_path)
    path = root / component_test_path("web-app")
    path.write_text(path.read_text() + "\n\ndef test_broken():\n    assert False\n")
    findings = _findings(root)
    assert [f.rule for f in findings] == ["FAILED_INTEGRATION_TEST"]
    assert "test_broken" in findings[0].message


def test_a_marker_naming_no_flow_is_reported(tmp_path):
    root = _assembled(tmp_path)
    write_flow_test(root, flow="checkout")
    assert _rules(root) == ["MISSING_FLOW_TEST", "UNKNOWN_FLOW", "UNTESTED_INTERFACE"]


def test_a_suite_that_writes_no_results_is_reported(tmp_path):
    root = _assembled(tmp_path)
    edit_plan(
        root,
        lambda p: p["integration"]["suites"]["integration"].update(results="build/nowhere.xml"),
    )
    assert _rules(root) == ["MISSING_FLOW_TEST", "MISSING_RESULTS", "UNTESTED_INTERFACE"]


def test_the_flow_test_lives_where_the_plan_says(tmp_path):
    root = _assembled(tmp_path)
    assert (root / FLOW_TEST).is_file()
