"""gates/swe/verify_log_events_gate.py — every log event asserted by a passing test."""

from product_builder import (
    FLOW_TEST,
    build_python_product,
    write_all_code,
    write_all_integration_tests,
    write_all_tests_and_stubs,
    write_events_code,
)

from gates.swe.verify_log_events_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def _assembled(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    write_events_code(root)
    write_all_integration_tests(root)
    return root


def test_gate_name_follows_the_convention():
    assert GATE == "verify_log_events_gate"


def test_events_named_by_a_passing_test_pass(tmp_path):
    assert _findings(_assembled(tmp_path)) == []


def test_without_tests_every_event_is_untested(tmp_path):
    findings = _findings(build_python_product(tmp_path))
    assert [f.rule for f in findings] == ["UNTESTED_EVENT"] * 3
    assert findings[0].file == "docs/requirements/login.md"
    assert "auth.signin.start" in findings[0].message


def test_an_event_the_test_does_not_name_is_reported(tmp_path):
    root = _assembled(tmp_path)
    path = root / FLOW_TEST
    path.write_text(path.read_text().replace("auth.signin.error", "auth.signin.failure"))
    findings = _findings(root)
    assert [f.rule for f in findings] == ["UNTESTED_EVENT"]
    assert "auth.signin.error" in findings[0].message


def test_a_test_without_the_requirement_marker_does_not_count(tmp_path):
    root = _assembled(tmp_path)
    path = root / FLOW_TEST
    path.write_text(path.read_text().replace(" @sdoc[REQ-0048]", ""))
    assert [f.rule for f in _findings(root)] == ["UNTESTED_EVENT"] * 3


def test_a_failing_test_does_not_count(tmp_path):
    root = _assembled(tmp_path)
    write_all_code(root)  # no events emitted: both flow tests fail
    assert [f.rule for f in _findings(root)] == ["UNTESTED_EVENT"] * 3
