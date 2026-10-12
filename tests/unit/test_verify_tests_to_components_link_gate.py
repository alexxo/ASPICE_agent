"""gates/swe/verify_tests_to_components_link_gate.py — every component tested on its own."""

from product_builder import (
    build_python_product,
    component_test_path,
    write_all_code,
    write_all_integration_tests,
    write_all_tests_and_stubs,
    write_component_test,
    write_events_code,
)

from gates.swe.verify_tests_to_components_link_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def _rules(root):
    return sorted(f.rule for f in _findings(root))


def _assembled(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    write_events_code(root)
    write_all_integration_tests(root)
    return root


def test_gate_name_follows_the_convention():
    assert GATE == "verify_tests_to_components_link_gate"


def test_components_with_passing_tests_pass(tmp_path):
    assert _rules(_assembled(tmp_path)) == []


def test_without_integration_tests_every_component_is_missing_one(tmp_path):
    root = build_python_product(tmp_path)
    findings = _findings(root)
    assert sorted(f.rule for f in findings) == ["MISSING_COMPONENT_TEST"] * 2
    assert {f.file for f in findings} == {"docs/architecture/auth-flow.md"}


def test_a_failing_component_test_does_not_count(tmp_path):
    root = _assembled(tmp_path)
    write_component_test(root, "web-app", assertion="run(1) == 5")
    assert _rules(root) == ["MISSING_COMPONENT_TEST"]


def test_a_marker_naming_no_component_is_reported(tmp_path):
    root = _assembled(tmp_path)
    path = root / component_test_path("web-app")
    path.write_text(path.read_text().replace("@component[web-app]", "@component[mailer]"))
    assert _rules(root) == ["MISSING_COMPONENT_TEST", "UNKNOWN_COMPONENT"]


def test_a_step_whose_selection_has_no_passing_test_is_reported(tmp_path):
    root = _assembled(tmp_path)
    (root / component_test_path("auth-service")).unlink()
    findings = _findings(root)
    assert sorted(f.rule for f in findings) == ["MISSING_COMPONENT_TEST", "UNTESTED_STEP"]
    step = next(f for f in findings if f.rule == "UNTESTED_STEP")
    assert "the auth service alone" in step.message
