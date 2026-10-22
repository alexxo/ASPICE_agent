"""gates/swe/check_design_contract_gate.py — the architecture follows diagram and requirements."""

from product_builder import STACK, architecture_doc, build_product

from gates.swe.check_design_contract_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def _rules(root):
    return sorted(f.rule for f in _findings(root))


def _arch(tmp_path, change):
    doc = architecture_doc()
    change(doc)
    return build_product(tmp_path, architecture=doc, stack=STACK, git=False)


def _component(doc, cid):
    return next(c for c in doc["components"] if c["id"] == cid)


def test_gate_name_follows_the_convention():
    assert GATE == "check_design_contract_gate"


def test_the_baseline_architecture_passes(tmp_path):
    assert _findings(build_product(tmp_path, stack=STACK, git=False)) == []


def test_no_architecture_fails_closed(tmp_path):
    root = build_product(tmp_path, stack=STACK, git=False)
    (root / "docs/architecture/auth-flow.md").unlink()
    assert _rules(root) == ["NO_ARCHITECTURE"]


def test_a_schema_violation_is_reported(tmp_path):
    root = _arch(tmp_path, lambda d: _component(d, "web-app").pop("budget"))
    assert _rules(root) == ["SCHEMA_VIOLATION"]


def test_a_component_without_a_size_is_reported(tmp_path):
    root = _arch(tmp_path, lambda d: _component(d, "web-app").pop("size"))
    assert _rules(root) == ["SCHEMA_VIOLATION"]


def test_a_duplicate_id_is_reported(tmp_path):
    root = _arch(tmp_path, lambda d: d["components"].append(dict(_component(d, "web-app"))))
    assert "DUPLICATE_ID" in _rules(root)


def test_a_component_from_no_diagram_node_is_reported(tmp_path):
    root = _arch(
        tmp_path, lambda d: _component(d, "web-app").update(derived_from="auth-flow#signin-request")
    )
    assert "UNKNOWN_ELEMENT" in _rules(root)


def test_a_node_without_a_component_is_reported(tmp_path):
    def change(doc):
        doc["components"] = [c for c in doc["components"] if c["id"] != "web-app"]
        _component(doc, "auth-service")["meets"].append("REQ-0049")
        doc["interfaces"] = []

    assert _rules(_arch(tmp_path, change)) == ["UNCOVERED_EDGE", "UNCOVERED_NODE"]


def test_an_interface_to_an_unknown_component_is_reported(tmp_path):
    root = _arch(tmp_path, lambda d: d["interfaces"][0].update(to="database"))
    assert _rules(root) == ["UNKNOWN_COMPONENT"]


def test_an_external_flag_that_contradicts_its_ends_is_reported(tmp_path):
    def change(doc):
        doc["interfaces"][0].update(external=True, security_templates=["authentication"])

    assert _rules(_arch(tmp_path, change)) == ["EXTERNAL_MISMATCH"]


def test_an_external_interface_names_its_security_templates(tmp_path):
    """Decision 25: the schema requires them once external is true."""
    root = _arch(tmp_path, lambda d: d["interfaces"][0].update(external=True))
    assert _rules(root) == ["EXTERNAL_MISMATCH", "SCHEMA_VIOLATION"]


def test_an_unmet_software_requirement_is_reported(tmp_path):
    root = _arch(tmp_path, lambda d: _component(d, "web-app").update(meets=["REQ-0050"]))
    findings = _findings(root)
    assert [f.rule for f in findings] == ["UNMET_REQUIREMENT"]
    assert findings[0].file == "docs/requirements/login.md"


def test_meeting_an_unknown_requirement_is_reported(tmp_path):
    root = _arch(tmp_path, lambda d: _component(d, "web-app")["meets"].append("REQ-9999"))
    assert _rules(root) == ["UNKNOWN_REQUIREMENT"]


def test_naming_an_unknown_decision_is_reported(tmp_path):
    root = _arch(tmp_path, lambda d: _component(d, "web-app").update(decisions=["ADR-0042"]))
    assert _rules(root) == ["UNKNOWN_DECISION"]


def test_a_component_without_modes_is_reported(tmp_path):
    root = _arch(tmp_path, lambda d: _component(d, "web-app").pop("modes"))
    assert _rules(root) == ["SCHEMA_VIOLATION"]


def test_a_component_without_concurrency_is_reported(tmp_path):
    root = _arch(tmp_path, lambda d: _component(d, "web-app").pop("concurrency"))
    assert _rules(root) == ["SCHEMA_VIOLATION"]


def test_a_transition_to_an_unknown_mode_is_reported(tmp_path):
    def change(doc):
        _component(doc, "auth-service")["modes"][0]["to"] = ["sleeping"]

    assert _rules(_arch(tmp_path, change)) == ["UNKNOWN_MODE"]
