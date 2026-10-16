"""gates/swe/verify_requirements_to_diagram_link_gate.py — requirements ↔ diagrams and wishes."""

import copy

from product_builder import ARCHITECTURE, SEQUENCE, baseline_requirements, build_product

from gates.swe.verify_requirements_to_diagram_link_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def _rules(root):
    return sorted(f.rule for f in _findings(root))


def _derived(tmp_path, uid, derived_from):
    reqs = baseline_requirements()
    next(r for r in reqs["login"] if r["uid"] == uid)["derived_from"] = derived_from
    return build_product(tmp_path, requirements=reqs)


def test_gate_name_follows_the_convention():
    assert GATE == "verify_requirements_to_diagram_link_gate"


def test_the_baseline_passes(product):
    assert _findings(product) == []


def test_an_unknown_diagram_is_reported(tmp_path):
    root = _derived(tmp_path, "REQ-0049", "checkout#user")
    assert "UNKNOWN_DIAGRAM" in _rules(root)


def test_an_unknown_element_is_reported_at_derived_from(tmp_path):
    root = _derived(tmp_path, "REQ-0047", "login#INV-9")
    findings = [f for f in _findings(root) if f.rule == "UNKNOWN_ELEMENT"]
    (finding,) = findings
    line = (root / finding.file).read_text().splitlines()[finding.line - 1]
    assert line.startswith("derived_from:")


def test_an_unknown_wish_is_reported(tmp_path):
    root = _derived(tmp_path, "REQ-0051", "W-99")
    assert _rules(root) == ["UNKNOWN_WISH"]


def test_an_uncovered_element_is_reported_at_its_source(tmp_path):
    reqs = baseline_requirements()
    reqs["login"] = [r for r in reqs["login"] if r["uid"] != "REQ-0014"]
    reqs["login"] = [r for r in reqs["login"] if r["uid"] != "REQ-0050"]
    root = build_product(tmp_path, requirements=reqs)
    (finding,) = _findings(root)
    assert finding.rule == "UNCOVERED_ELEMENT"
    assert finding.file == "docs/diagrams/auth-flow.architecture.json"
    assert "signin-request" in finding.message


def test_an_uncovered_invariant_points_at_the_invariants_file(tmp_path):
    reqs = baseline_requirements()
    next(r for r in reqs["login"] if r["uid"] == "REQ-0047")["derived_from"] = "login#web-app"
    root = build_product(tmp_path, requirements=reqs)
    (finding,) = _findings(root)
    assert (finding.rule, finding.file) == (
        "UNCOVERED_ELEMENT",
        "docs/diagrams/login.invariants.yaml",
    )


def test_messages_need_no_requirement_of_their_own(product):
    """Messages produce acceptance criteria, not requirements (SWE.1 BP1)."""
    assert not any("submit-credentials" in f.message for f in _findings(product))


def test_an_unreadable_diagram_is_reported_once(tmp_path):
    architecture = copy.deepcopy(ARCHITECTURE)
    del architecture["connections"][0]["label"]
    root = build_product(
        tmp_path,
        diagrams={"auth-flow.architecture.json": architecture, "login.sequence.json": SEQUENCE},
    )
    assert _rules(root) == ["DIAGRAM_UNREADABLE"]


def test_no_diagrams_fails_closed(tmp_path):
    root = build_product(tmp_path, diagrams={}, invariants={})
    assert "NO_DIAGRAMS" in _rules(root)


def test_a_software_requirement_from_the_picture_is_a_level_mismatch(tmp_path):
    root = _derived(tmp_path, "REQ-0047", "auth-flow#auth-service")
    findings = [f for f in _findings(root) if f.rule == "LEVEL_MISMATCH"]
    (finding,) = findings
    line = (root / finding.file).read_text().splitlines()[finding.line - 1]
    assert line.startswith("level:")
    assert "sequence" in finding.message


def test_a_mismatched_requirement_covers_nothing(tmp_path):
    reqs = baseline_requirements()
    next(r for r in reqs["login"] if r["uid"] == "REQ-0011")["level"] = "software"
    next(r for r in reqs["login"] if r["uid"] == "REQ-0011")["refines"] = "REQ-0012"
    root = build_product(tmp_path, requirements=reqs)
    rules = _rules(root)
    assert "LEVEL_MISMATCH" in rules
    assert "UNCOVERED_ELEMENT" in rules
