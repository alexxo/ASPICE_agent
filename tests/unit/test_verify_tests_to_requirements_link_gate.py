"""gates/swe/verify_tests_to_requirements_link_gate.py — every unit tested, every test passing."""

from product_builder import (
    build_python_product,
    write_all_code,
    write_all_tests_and_stubs,
    write_unit_test,
)

from gates.swe.verify_tests_to_requirements_link_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _built(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    return root


def test_gate_name_follows_the_convention():
    assert GATE == "verify_tests_to_requirements_link_gate"


def test_every_unit_with_a_passing_test_passes(tmp_path):
    assert _rules(_built(tmp_path)) == []


def test_a_failing_test_leaves_its_unit_untested(tmp_path):
    root = _built(tmp_path)
    write_unit_test(root, "auth-service", "count-failures", assertion="run(1) == 3")
    assert _rules(root) == ["FAILED_TEST", "UNTESTED_UNIT"]


def test_a_unit_without_a_test_is_reported(tmp_path):
    root = _built(tmp_path)
    (root / "src" / "web_app" / "test_signin_form.py").unlink()
    (root / "src" / "web_app" / "test_signin_form_security.py").unlink()
    assert _rules(root) == ["UNTESTED_UNIT"]


def test_a_result_matching_no_test_file_is_reported(tmp_path):
    root = _built(tmp_path)
    (root / "src" / "web_app" / "extra_check.py").write_text(
        "# @unit[signin-form]\n\n\ndef test_hidden():\n    assert True\n"
    )
    stack_file = root / "docs" / "architecture" / "stack.yaml"
    stack_file.write_text(
        stack_file.read_text().replace("--cov=src", "--cov=src -o python_files=*.py")
    )
    assert _rules(root) == ["UNMAPPED_RESULT"]


def test_a_skipped_test_does_not_test_its_unit(tmp_path):
    root = _built(tmp_path)
    (root / "src" / "web_app" / "test_signin_form.py").write_text(
        "# @unit[signin-form]\nimport pytest\n\n\n"
        "@pytest.mark.skip(reason='later')\ndef test_signin_form():\n    assert False\n"
    )
    (root / "src" / "web_app" / "test_signin_form_security.py").unlink()
    assert _rules(root) == ["UNTESTED_UNIT"]
