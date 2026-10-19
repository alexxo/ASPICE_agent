"""tools/validate_contract_tool.py — checks a record against a contract."""

import pytest

from tools.validate_contract_tool import ContractNotFound, validate

VALID_FINDINGS = {"gate": "check_glossary_gate", "result": "pass", "findings": []}


def test_a_valid_record_has_no_violations():
    assert validate(VALID_FINDINGS, "findings") == []


def test_violations_carry_path_keyword_and_message():
    record = dict(VALID_FINDINGS, gate="glossary-gate")
    (violation,) = validate(record, "findings")
    assert violation.path == "gate"
    assert violation.keyword == "pattern"
    assert "glossary-gate" in violation.message


def test_a_record_violation_has_an_empty_path():
    record = {"gate": "check_glossary_gate", "result": "pass"}
    (violation,) = validate(record, "findings")
    assert (violation.path, violation.keyword) == ("", "required")


def test_violations_come_in_a_fixed_order():
    record = {"gate": "glossary-gate", "result": "maybe", "findings": [], "extra": 1}
    first = validate(record, "findings")
    assert first == validate(record, "findings")
    assert [v.path for v in first] == sorted(v.path for v in first)


def test_every_contract_in_the_tree_can_be_loaded(repo_root):
    for schema in (repo_root / "contracts").glob("*_contract.v*.schema.json"):
        name = schema.name.split("_contract.v")[0]
        validate({}, name)  # must not raise


def test_an_unknown_contract_is_an_error():
    with pytest.raises(ContractNotFound):
        validate({}, "no_such")
