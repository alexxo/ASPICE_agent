"""gates/swe/verify_software_tests_to_requirements_link_gate.py — every requirement tested."""

from product_builder import (
    E2E_TEST,
    SOFTWARE_TEST,
    build_python_product,
    python_stack,
    write_all_code,
    write_all_software_tests,
    write_all_tests_and_stubs,
    write_e2e_test,
)

from gates.swe.verify_software_tests_to_requirements_link_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def _rules(root):
    return sorted(f.rule for f in _findings(root))


def _verified(tmp_path, stack=None):
    root = build_python_product(tmp_path, stack=stack)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    write_all_software_tests(root)
    return root


def test_gate_name_follows_the_convention():
    assert GATE == "verify_software_tests_to_requirements_link_gate"


def test_every_requirement_tested_in_its_suite_passes(tmp_path):
    assert _rules(_verified(tmp_path)) == []


def test_without_tests_every_tested_requirement_is_unverified(tmp_path):
    findings = _findings(build_python_product(tmp_path))
    # five system-level and three software-level; constraints and measured ones are not here
    assert [f.rule for f in findings] == ["UNVERIFIED_REQUIREMENT"] * 8
    assert findings[0].file == "docs/requirements/login.md"
    assert "REQ-0011" in findings[0].message and "e2e suite" in findings[0].message


def test_a_requirement_whose_marker_is_removed_is_unverified(tmp_path):
    root = _verified(tmp_path)
    path = root / SOFTWARE_TEST
    path.write_text(path.read_text().replace(" @sdoc[REQ-0050]", ""))
    findings = _findings(root)
    assert [f.rule for f in findings] == ["UNVERIFIED_REQUIREMENT"]
    assert "REQ-0050" in findings[0].message


def test_a_system_requirement_tested_only_in_the_software_suite_is_unverified(tmp_path):
    root = _verified(tmp_path)
    path = root / SOFTWARE_TEST
    path.write_text(
        path.read_text().replace("# @sdoc[REQ-0049]", "# @sdoc[REQ-0049] @sdoc[REQ-0011]")
    )
    e2e = root / E2E_TEST
    e2e.write_text(e2e.read_text().replace("@sdoc[REQ-0011] ", ""))
    findings = _findings(root)
    assert [f.rule for f in findings] == ["UNVERIFIED_REQUIREMENT"]
    assert "REQ-0011" in findings[0].message


def test_a_marker_naming_no_requirement_is_reported(tmp_path):
    root = _verified(tmp_path)
    path = root / SOFTWARE_TEST
    path.write_text(path.read_text().replace("@sdoc[REQ-0049]", "@sdoc[REQ-0049] @sdoc[REQ-9999]"))
    findings = _findings(root)
    assert [f.rule for f in findings] == ["UNKNOWN_REQUIREMENT"]
    assert findings[0].file == SOFTWARE_TEST and findings[0].line == 1


def test_a_failing_test_is_reported_and_its_requirements_unverified(tmp_path):
    root = _verified(tmp_path)
    write_e2e_test(root, assertion="run(1) == 3")
    assert _rules(root) == ["FAILED_TEST", *["UNVERIFIED_REQUIREMENT"] * 5]


def test_a_missing_e2e_suite_has_no_results(tmp_path):
    stack = python_stack()
    del stack["suites"]["e2e"]
    root = _verified(tmp_path, stack=stack)
    findings = _findings(root)
    assert sorted(f.rule for f in findings) == ["MISSING_RESULTS", *["UNVERIFIED_REQUIREMENT"] * 5]
    missing = next(f for f in findings if f.rule == "MISSING_RESULTS")
    assert missing.file == "docs/architecture/stack.yaml" and "e2e" in missing.message
