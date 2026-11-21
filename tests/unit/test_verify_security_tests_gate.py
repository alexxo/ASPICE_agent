"""gates/swe/verify_security_tests_gate.py — every trust boundary has its security tests."""

from product_builder import (
    SECURITY_TEST,
    build_python_product,
    write_all_code,
    write_all_tests_and_stubs,
    write_security_test,
)

from gates.swe.verify_security_tests_gate import GATE, catalog, check, guarded_ends
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


def test_the_boundary_follows_the_ends_not_the_external_flag(tmp_path):
    """A wrong flag is check_design_contract_gate's EXTERNAL_MISMATCH; the test stays required."""
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    path = root / ARCHITECTURE
    path.write_text(path.read_text().replace("external: true", "external: false"))
    assert _rules(root) == ["MISSING_SECURITY_TEST"]


def _untrusted_web_app(root, *names):
    """The web app runs in the visitor's browser; its call to the auth service
    asks for these templates."""
    path = root / ARCHITECTURE
    listed = "".join(f"- {n}\n" for n in names)
    text = path.read_text().replace("name: Web app\n", "name: Web app\nruns_in: untrusted\n")
    path.write_text(
        text.replace(
            "data: email and password\n", f"data: email and password\nsecurity_templates:\n{listed}"
        )
    )


def test_a_call_from_an_untrusted_component_needs_the_callees_security_tests(tmp_path):
    """FB-9: anyone can call what the browser calls, so the auth service is a boundary."""
    root = _built(tmp_path)
    _untrusted_web_app(root, "authentication")
    (finding,) = _findings(root)
    assert finding.rule == "MISSING_SECURITY_TEST"
    assert "signin-request" in finding.message and "auth-service" in finding.message


def test_the_trusted_end_is_guarded_and_the_untrusted_end_by_its_external_one():
    components = {
        "user": {"role": "external"},
        "browser": {"role": "component", "runs_in": "untrusted"},
        "backend": {"role": "component"},
        "worker": {"role": "component"},
        "partner": {"role": "external"},
    }

    def ends(a, b):
        return guarded_ends({"from": a, "to": b}, components)

    assert ends("user", "browser") == ["browser"]
    assert ends("browser", "backend") == ["backend"]
    assert ends("backend", "browser") == ["backend"]
    assert ends("backend", "worker") == []
    assert ends("browser", "browser") == []
    assert ends("user", "partner") == []
