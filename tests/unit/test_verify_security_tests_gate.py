"""gates/swe/verify_security_tests_gate.py — every trust boundary has its security tests."""

from product_builder import (
    SECURITY_TEST,
    build_python_product,
    write_all_code,
    write_all_tests_and_stubs,
    write_security_test,
)

from gates.swe.verify_security_tests_gate import GATE, catalog, check
from tools.read_product_config_tool import read_product_config

ARCHITECTURE = "docs/architecture/auth-flow.md"


def _findings(root):
    return check(read_product_config(root))


def _rules(root):
    return sorted(f.rule for f in _findings(root))


def _built(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    return root


def _templates(root, *names):
    """The external interface of the fixture asks for these templates instead."""
    path = root / ARCHITECTURE
    listed = "".join(f"- {n}\n" for n in names)
    path.write_text(path.read_text().replace("- input-validation\n", listed))


def test_gate_name_follows_the_convention():
    assert GATE == "verify_security_tests_gate"


def test_the_catalog_holds_the_five_templates():
    assert catalog() == [
        "authentication",
        "authorization",
        "input-validation",
        "stored-data",
        "outbound-calls",
    ]


def test_a_boundary_with_its_passing_security_test_passes(tmp_path):
    assert _rules(_built(tmp_path)) == []


def test_a_boundary_without_a_security_test_is_reported(tmp_path):
    root = _built(tmp_path)
    (root / SECURITY_TEST).unlink()
    (finding,) = _findings(root)
    assert finding.rule == "MISSING_SECURITY_TEST"
    assert (finding.file, finding.line is not None) == (ARCHITECTURE, True)
    assert "browse" in finding.message and "web-app" in finding.message


def test_a_security_test_that_fails_does_not_count(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)  # red on the stubs
    assert _rules(root) == ["MISSING_SECURITY_TEST"]


def test_each_template_the_interface_names_needs_its_own_test(tmp_path):
    root = _built(tmp_path)
    _templates(root, "input-validation", "authentication")
    (finding,) = _findings(root)
    assert finding.rule == "MISSING_SECURITY_TEST"
    assert "@security[authentication]" in finding.message


def test_a_security_test_of_another_component_does_not_count(tmp_path):
    root = _built(tmp_path)
    path = root / SECURITY_TEST
    path.write_text(path.read_text().replace("@unit[signin-form]", "@unit[count-failures]"))
    assert _rules(root) == ["MISSING_SECURITY_TEST"]


def test_a_marker_naming_no_template_is_reported(tmp_path):
    root = _built(tmp_path)
    write_security_test(root, template="sql-injection")
    rules = _rules(root)
    assert rules == ["MISSING_SECURITY_TEST", "UNKNOWN_TEMPLATE"]


def test_a_template_no_interface_asks_for_is_allowed(tmp_path):
    root = _built(tmp_path)
    path = root / SECURITY_TEST
    path.write_text(path.read_text().replace("]\n", "] @security[authorization]\n", 1))
    assert _rules(root) == []


def test_without_an_external_interface_nothing_is_required(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    path = root / ARCHITECTURE
    path.write_text(path.read_text().replace("external: true", "external: false"))
    assert _rules(root) == []
