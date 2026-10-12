"""gates/swe/check_observability_gate.py — every observability requirement watched."""

from product_builder import OBSERVABILITY, build_python_product, write_observability

from gates.swe.check_observability_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def test_gate_name_follows_the_convention():
    assert GATE == "check_observability_gate"


def test_a_watched_requirement_passes(tmp_path):
    root = build_python_product(tmp_path)
    write_observability(root)
    assert _findings(root) == []


def test_an_unwatched_requirement_is_reported(tmp_path):
    findings = _findings(build_python_product(tmp_path))
    assert [f.rule for f in findings] == ["UNOBSERVED_REQUIREMENT"]
    assert findings[0].file == "docs/requirements/login.md" and "REQ-0048" in findings[0].message


def test_a_definition_naming_no_requirement_is_reported(tmp_path):
    root = build_python_product(tmp_path)
    write_observability(root)
    path = root / OBSERVABILITY
    path.write_text(path.read_text().replace("REQ-0048", "REQ-9999"))
    findings = _findings(root)
    assert sorted(f.rule for f in findings) == ["UNKNOWN_REQUIREMENT", "UNOBSERVED_REQUIREMENT"]
    unknown = next(f for f in findings if f.rule == "UNKNOWN_REQUIREMENT")
    assert unknown.file == OBSERVABILITY and unknown.line == 1
