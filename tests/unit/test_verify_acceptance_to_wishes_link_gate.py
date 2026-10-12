"""gates/val/verify_acceptance_to_wishes_link_gate.py — every wish has its scenario."""

import pytest
from product_builder import (
    ALL_SCENARIOS,
    DEMO,
    SCENARIO_TESTS,
    build_releasable_product,
    commit_all,
    passed,
    propose_release,
    record_validation,
    tag_release,
)

from gates.val.verify_acceptance_to_wishes_link_gate import GATE, check
from tools.read_product_config_tool import read_product_config

RECORD = "validation/records/1.0.0.yaml"


@pytest.fixture
def product(tmp_path, monkeypatch):
    root, host = build_releasable_product(tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return root


def findings(root):
    return sorted((f.rule, f.file, f.line) for f in check(read_product_config(root)))


def rules(root):
    return [(rule, file) for rule, file, _ in findings(root)]


def test_gate_name_follows_the_convention():
    assert GATE == "verify_acceptance_to_wishes_link_gate"


def test_every_wish_with_a_scenario_passes(product):
    assert findings(product) == []


def test_a_wish_without_a_scenario_is_reported_at_the_wish(product):
    (product / SCENARIO_TESTS["W-03"]).unlink()
    assert findings(product) == [("MISSING_SCENARIO", "docs/wishes.md", 16)]


def test_a_marker_naming_no_wish_is_reported_at_its_line(product):
    (product / "validation/scenarios/test_ghost.py").write_text("\n# @wish[W-09]\n")
    assert findings(product) == [("UNKNOWN_WISH", "validation/scenarios/test_ghost.py", 2)]


def test_a_file_naming_no_wish_is_no_scenario(product):
    (product / DEMO).write_text("The demo lost its marker.\n")
    assert rules(product) == [("MISSING_SCENARIO", "docs/wishes.md")]


def test_a_release_covers_every_wish_it_affects(product):
    propose_release(product)
    record_validation(product, passed(SCENARIO_TESTS["W-01"]))
    assert rules(product) == [("UNVALIDATED_WISH", RECORD), ("UNVALIDATED_WISH", RECORD)]


def test_a_release_with_a_result_per_wish_passes(product):
    propose_release(product)
    record_validation(product, passed(*ALL_SCENARIOS))
    assert findings(product) == []


def test_a_release_that_changes_only_tests_affects_no_wish(product):
    propose_release(product)
    record_validation(product, passed(*ALL_SCENARIOS))
    tag_release(product, "1.0.0")
    (product / "it").mkdir(exist_ok=True)
    (product / "it/test_more.py").write_text("def test_more():\n    assert True\n")
    commit_all(product, "test: one more integration test #3")
    propose_release(product, "1.0.1")
    record_validation(product, passed(SCENARIO_TESTS["W-01"]), version="1.0.1")
    assert findings(product) == []


def test_a_release_that_changes_the_code_affects_every_wish(product):
    propose_release(product)
    record_validation(product, passed(*ALL_SCENARIOS))
    tag_release(product, "1.0.0")
    (product / "src/fix.py").write_text("FIX = 1\n")
    commit_all(product, "fix: a fix #3")
    propose_release(product, "1.0.1")
    record_validation(product, passed(SCENARIO_TESTS["W-01"]), version="1.0.1")
    assert [r for r, _ in rules(product)] == ["UNVALIDATED_WISH", "UNVALIDATED_WISH"]


def test_an_unreadable_record_is_left_to_the_evidence_gate(product):
    propose_release(product)
    (product / "validation/records").mkdir(parents=True)
    (product / RECORD).write_text("results: [\n")
    assert findings(product) == []
