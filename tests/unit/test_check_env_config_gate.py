"""gates/swe/check_env_config_gate.py — environment variables declared, read and validated."""

from product_builder import (
    SETTINGS,
    SETTINGS_TEST,
    build_python_product,
    python_stack,
    write_all_code,
    write_all_tests_and_stubs,
)

from gates.swe.check_env_config_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _built(tmp_path, stack=None):
    root = build_python_product(tmp_path, stack=stack)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    return root


def test_gate_name_follows_the_convention():
    assert GATE == "check_env_config_gate"


def test_declared_read_and_validated_variables_pass(tmp_path):
    assert _rules(_built(tmp_path)) == []


def test_a_variable_read_but_not_declared_is_reported(tmp_path):
    root = _built(tmp_path)
    path = root / SETTINGS
    path.write_text(path.read_text() + '\n\ndef timeout():\n    return os.environ["TIMEOUT"]\n')
    assert _rules(root) == ["UNDECLARED_VARIABLE"]


def test_a_declared_variable_no_code_reads_is_reported(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)  # the stub reads nothing, and its test fails
    assert _rules(root) == ["UNTESTED_VARIABLE", "UNUSED_VARIABLE"]


def test_a_required_variable_without_a_passing_test_is_reported(tmp_path):
    root = _built(tmp_path)
    (root / SETTINGS_TEST).unlink()
    assert _rules(root) == ["UNTESTED_VARIABLE"]


def test_an_env_marker_naming_no_variable_is_reported(tmp_path):
    root = _built(tmp_path)
    path = root / SETTINGS_TEST
    path.write_text(
        path.read_text().replace("@env[SESSION_SECRET]", "@env[SESSION_SECRET] @env[NOPE]")
    )
    assert _rules(root) == ["UNKNOWN_VARIABLE"]


def test_a_read_pattern_without_one_group_is_reported(tmp_path):
    stack = python_stack()
    stack["env_read_patterns"].append(r"getenv\(\w+\)")
    stack["env_read_patterns"].append(r"([unclosed")
    assert _rules(_built(tmp_path, stack)) == ["INVALID_READ_PATTERN", "INVALID_READ_PATTERN"]


def test_without_patterns_no_read_is_seen(tmp_path):
    stack = python_stack()
    stack["env_read_patterns"] = []
    assert _rules(_built(tmp_path, stack)) == ["UNUSED_VARIABLE"]
