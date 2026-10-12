"""gates/swe/check_requirements_contract_gate.py — the requirement contract across all files."""

from product_builder import baseline_requirements, build_product

from gates.swe.check_requirements_contract_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def _rules(root):
    return sorted(f.rule for f in _findings(root))


def _with(tmp_path, change):
    reqs = baseline_requirements()
    change(reqs["login"])
    return build_product(tmp_path, requirements=reqs)


def _by_uid(reqs, uid):
    return next(r for r in reqs if r["uid"] == uid)


def test_gate_name_follows_the_convention():
    assert GATE == "check_requirements_contract_gate"


def test_the_baseline_passes(product):
    assert _findings(product) == []


def test_no_requirements_fails_closed(tmp_path):
    root = build_product(tmp_path, requirements={})
    assert _rules(root) == ["NO_REQUIREMENTS"]


def test_a_schema_violation_points_at_the_field(tmp_path):
    root = _with(tmp_path, lambda r: _by_uid(r, "REQ-0011").update(size="XXL"))
    (finding,) = _findings(root)
    assert finding.rule == "SCHEMA_VIOLATION"
    assert finding.file == "docs/requirements/login.md"
    line = (root / finding.file).read_text().splitlines()[finding.line - 1]
    assert line.startswith("size:")
    assert "REQ-0011" in finding.message


def test_an_unreadable_block_is_reported(tmp_path):
    root = build_product(tmp_path)
    path = root / "docs/requirements/broken.md"
    path.write_text("```yaml requirement\nuid: REQ-0090\nstatement: [unclosed\n```\n")
    findings = _findings(root)
    assert [(f.rule, f.file, f.line) for f in findings] == [
        ("UNREADABLE_REQUIREMENT", "docs/requirements/broken.md", 3)
    ]


def test_a_duplicate_uid_is_reported_at_the_second_occurrence(tmp_path):
    def change(reqs):
        copy = dict(_by_uid(reqs, "REQ-0049"))
        reqs.append(copy)

    root = _with(tmp_path, change)
    (finding,) = _findings(root)
    assert finding.rule == "DUPLICATE_UID"
    assert "REQ-0049" in finding.message


def test_an_unknown_parent_is_reported(tmp_path):
    root = _with(tmp_path, lambda r: _by_uid(r, "REQ-0049").update(refines="REQ-9999"))
    assert "UNKNOWN_PARENT" in _rules(root)


def test_a_software_parent_is_reported(tmp_path):
    root = _with(tmp_path, lambda r: _by_uid(r, "REQ-0049").update(refines="REQ-0050"))
    assert "PARENT_NOT_SYSTEM" in _rules(root)


def test_an_unrefined_system_requirement_is_reported(tmp_path):
    root = _with(tmp_path, lambda r: r.remove(_by_uid(r, "REQ-0049")))
    (finding,) = _findings(root)
    assert finding.rule == "UNREFINED_SYSTEM_REQUIREMENT"
    assert "REQ-0011" in finding.message


def test_a_feature_without_observability_is_reported(tmp_path):
    def change(reqs):
        obs = _by_uid(reqs, "REQ-0048")
        reqs.remove(obs)

    root = _with(tmp_path, change)
    (finding,) = _findings(root)
    assert finding.rule == "MISSING_OBSERVABILITY"
    assert finding.file == "docs/diagrams/login.sequence.json"


def test_an_invalid_block_does_not_cascade(tmp_path):
    """REQ-0049 breaks the schema but still refines REQ-0011: one finding, not two."""
    root = _with(tmp_path, lambda r: _by_uid(r, "REQ-0049").update(size="XXL"))
    assert _rules(root) == ["SCHEMA_VIOLATION"]


def test_a_requirement_without_a_happy_case_is_reported(tmp_path):
    def change(reqs):
        for criterion in _by_uid(reqs, "REQ-0049")["acceptance_criteria"]:
            criterion["case"] = "error"

    root = _with(tmp_path, change)
    (finding,) = _findings(root)
    assert finding.rule == "MISSING_HAPPY_CASE"
    assert "REQ-0049" in finding.message


def test_a_high_criticality_requirement_without_an_error_case_is_reported(tmp_path):
    def change(reqs):
        req = _by_uid(reqs, "REQ-0049")
        req["acceptance_criteria"] = [c for c in req["acceptance_criteria"] if c["case"] == "happy"]

    root = _with(tmp_path, change)
    (finding,) = _findings(root)
    assert finding.rule == "MISSING_ERROR_CASE"


def test_an_edge_case_counts_as_well_as_an_error_case(tmp_path):
    def change(reqs):
        for criterion in _by_uid(reqs, "REQ-0049")["acceptance_criteria"]:
            if criterion["case"] == "error":
                criterion["case"] = "edge"

    assert _findings(_with(tmp_path, change)) == []


def test_a_medium_criticality_requirement_needs_only_a_happy_case(tmp_path):
    def change(reqs):
        req = _by_uid(reqs, "REQ-0049")
        req["criticality"] = "medium"
        req["acceptance_criteria"] = [c for c in req["acceptance_criteria"] if c["case"] == "happy"]

    assert _findings(_with(tmp_path, change)) == []
