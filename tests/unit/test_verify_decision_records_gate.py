"""gates/swe/verify_decision_records_gate.py — every decision record well-formed and consistent."""

import copy

from product_builder import AGENT_DECISION as AGENT
from product_builder import DECISIONS, STACK, build_product
from product_builder import PERSON_DECISION as PERSON

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


# --- who decides: the person on a critical requirement, the agent otherwise -------------


def _who(tmp_path, *records, page=True):
    from product_builder import baseline_requirements

    from agent.render_decisions_tool import render_decisions

    requirements = baseline_requirements()
    for records_of_file in requirements.values():
        for req in records_of_file:
            if req["uid"] == "REQ-0011":
                req["criticality"] = "low"
    decisions = copy.deepcopy(DECISIONS)
    for record in records:
        decisions[f"{record['id'][4:]}-record"] = copy.deepcopy(record)
    root = build_product(
        tmp_path, stack=STACK, decisions=decisions, requirements=requirements, git=False
    )
    if page:
        render_decisions(root)
    return root


def test_the_agent_and_the_person_deciding_pass(tmp_path):
    assert _rules(_who(tmp_path, AGENT, PERSON)) == []


def test_a_record_lacking_what_its_card_needs_is_reported(tmp_path):
    lacking = {k: v for k, v in AGENT.items() if k != "where"}
    assert _rules(_who(tmp_path, lacking)) == ["INCOMPLETE_DECISION"]


def test_the_person_s_answered_record_names_who_answered(tmp_path):
    accepted = {k: v for k, v in PERSON.items() if k != "proposed_because"}
    assert _rules(_who(tmp_path, {**accepted, "status": "accepted"})) == ["INCOMPLETE_DECISION"]


def test_a_record_serving_no_requirement_of_the_product_is_reported(tmp_path):
    assert _rules(_who(tmp_path, {**AGENT, "requirements": ["REQ-0999"]})) == [
        "UNKNOWN_REQUIREMENT"
    ]


def test_the_agent_deciding_a_critical_requirement_is_reported(tmp_path):
    assert _rules(_who(tmp_path, {**AGENT, "requirements": ["REQ-0012"]})) == [
        "AGENT_DECIDED_CRITICAL"
    ]


def test_a_missing_decisions_page_is_reported(tmp_path):
    assert _rules(_who(tmp_path, AGENT, page=False)) == ["MISSING_DECISIONS_PAGE"]


def test_an_outdated_decisions_page_is_reported(tmp_path):
    root = _who(tmp_path, AGENT)
    record = root / "docs/decisions/0002-record.md"
    record.write_text(record.read_text().replace("top to bottom", "downwards"))
    assert _rules(root) == ["DECISIONS_PAGE_OUTDATED"]
