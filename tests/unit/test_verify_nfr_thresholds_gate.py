"""gates/swe/verify_nfr_thresholds_gate.py — every measured value meets its threshold."""

from product_builder import (
    BENCH_TEST,
    build_python_product,
    edit_plan,
    write_all_code,
    write_all_software_tests,
    write_all_tests_and_stubs,
    write_bench_test,
)

from gates.swe.verify_nfr_thresholds_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def _measured(tmp_path, stack=None):
    root = build_python_product(tmp_path, stack=stack)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    write_all_software_tests(root)
    return root


def test_gate_name_follows_the_convention():
    assert GATE == "verify_nfr_thresholds_gate"


def test_values_within_their_thresholds_pass(tmp_path):
    assert _findings(_measured(tmp_path)) == []


def test_without_measurements_every_measured_requirement_is_missing(tmp_path):
    findings = _findings(build_python_product(tmp_path))
    assert [f.rule for f in findings] == ["MISSING_MEASUREMENT"] * 3
    assert findings[0].file == "docs/requirements/login.md"
    assert "REQ-0047" in findings[0].message and "bench" in findings[0].message


def test_a_value_beyond_its_threshold_is_reported(tmp_path):
    root = _measured(tmp_path)
    write_bench_test(root, value="run(5)")  # 6 failed sign-ins, threshold <= 5
    findings = _findings(root)
    assert [f.rule for f in findings] == ["THRESHOLD_NOT_MET"] * 3
    assert "measured 6" in findings[0].message and "<= 5" in findings[0].message


def test_a_value_in_another_unit_is_no_measurement(tmp_path):
    root = _measured(tmp_path)
    path = root / BENCH_TEST
    path.write_text(path.read_text().replace('"value": run(4)}', '"value": run(4), "unit": "ms"}'))
    assert [f.rule for f in _findings(root)] == ["MISSING_MEASUREMENT"] * 3


def test_a_suite_without_a_measurements_path_measures_nothing(tmp_path):
    root = _measured(tmp_path)
    edit_plan(root, lambda p: p["software"]["suites"]["bench"].pop("measurements"))
    assert [f.rule for f in _findings(root)] == ["MISSING_MEASUREMENT"] * 3


def test_a_measurements_file_that_breaks_the_contract_is_reported(tmp_path):
    root = _measured(tmp_path)
    path = root / BENCH_TEST
    path.write_text(path.read_text().replace('"measurements.v1"', '"measurements.v0"'))
    findings = _findings(root)
    assert sorted(f.rule for f in findings) == ["MISSING_MEASUREMENT"] * 3 + ["SCHEMA_VIOLATION"]
