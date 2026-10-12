"""gates/swe/verify_decision_records_gate.py — every decision record well-formed and consistent."""

import copy

from product_builder import DECISIONS, STACK, build_product

from gates.swe.verify_decision_records_gate import GATE, check
from tools.read_product_config_tool import read_product_config

NAME = "0001-java-for-the-auth-service"


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _decisions(tmp_path, change):
    decisions = copy.deepcopy(DECISIONS)
    change(decisions)
    return build_product(tmp_path, stack=STACK, decisions=decisions, git=False)


def test_gate_name_follows_the_convention():
    assert GATE == "verify_decision_records_gate"


def test_the_baseline_records_pass(tmp_path):
    assert _rules(build_product(tmp_path, stack=STACK, git=False)) == []


def test_no_records_is_nothing_to_verify(product):
    assert _rules(product) == []


def test_a_record_breaking_its_contract_is_reported(tmp_path):
    root = _decisions(tmp_path, lambda d: d[NAME]["options"].pop())
    assert _rules(root) == ["SCHEMA_VIOLATION"]


def test_a_file_without_a_decision_block_is_reported(tmp_path):
    root = build_product(tmp_path, stack=STACK, git=False)
    (root / "docs/decisions/0002-empty.md").write_text("# Nothing here\n")
    assert _rules(root) == ["UNREADABLE_DECISION"]


def test_a_file_name_not_matching_the_id_is_reported(tmp_path):
    root = _decisions(tmp_path, lambda d: d[NAME].update(id="ADR-0002"))
    assert "FILE_NAME_MISMATCH" in _rules(root)


def test_a_duplicate_id_is_reported(tmp_path):
    root = _decisions(tmp_path, lambda d: d.update({"0001-again": copy.deepcopy(d[NAME])}))
    assert _rules(root) == ["DUPLICATE_DECISION"]


def test_a_choice_that_is_not_an_option_is_reported(tmp_path):
    root = _decisions(tmp_path, lambda d: d[NAME].update(choice="Rust"))
    assert _rules(root) == ["CHOICE_NOT_AN_OPTION"]


def test_superseding_an_unknown_record_is_reported(tmp_path):
    root = _decisions(tmp_path, lambda d: d[NAME].update(supersedes="ADR-0007"))
    assert _rules(root) == ["UNKNOWN_SUPERSEDED"]
