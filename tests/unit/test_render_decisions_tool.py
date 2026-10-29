"""agent/render_decisions_tool.py — every decision on one page; the person's asked as the card."""

import copy
from datetime import date

import pytest
from product_builder import AGENT_DECISION as AGENT
from product_builder import DECISIONS, STACK, baseline_requirements, build_product
from product_builder import PERSON_DECISION as PERSON

from agent.render_decisions_tool import (
    choice_of,
    main,
    read_decisions,
    record_answer,
    render,
)
from tools.read_product_config_tool import read_product_config


def _product(tmp_path, *records):
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
    return read_product_config(root)


def _records(config):
    return {key: data for key, (_, data) in read_decisions(config).items()}


def test_the_page_has_the_four_sections_in_order(tmp_path):
    page = render(_product(tmp_path, AGENT, PERSON))
    headings = [
        "Waiting for you (1)",
        "Answered by you (0)",
        "Decided by the agent (1)",
        "Recorded with the architecture (1)",
    ]
    places = [page.index(h) for h in headings]
    assert places == sorted(places)
    assert "<b>1 waits for you.</b>" in page
    assert "<details" not in page


def test_the_agent_s_card_says_why_it_is_not_critical_and_where(tmp_path):
    page = render(_product(tmp_path, AGENT))
    assert "Only the order of two fields; rated low." in page
    assert "src/web/form.py:12" in page
    assert "REQ-0011 low · ADR-0002" in page


def test_a_superseded_choice_is_shown_as_before_and_not_asked_again(tmp_path):
    old = {**PERSON, "id": "ADR-0004", "status": "superseded", "choice": "password first"}
    old["answered_by"] = "Alex"
    new = {**PERSON, "supersedes": "ADR-0004"}
    config = _product(tmp_path, old, new)
    page = render(config)
    assert page.count("After a lockout, who may unlock the account?") == 1
    assert "On 2026-10-29 you answered: password first." in page
    assert (
        choice_of(new, _records(config))["before"] == "On 2026-10-29 you answered: password first."
    )


def test_the_person_s_decision_is_the_card_with_its_proposal(tmp_path):
    config = _product(tmp_path, PERSON)
    choice = choice_of(PERSON, _records(config))
    assert choice["select"] == ["email first", "password first"]
    assert choice["proposal"] == {"choice": 1, "why": PERSON["proposed_because"]}
    assert choice["why_you"] == PERSON["why_you"]


def test_the_answer_is_recorded_and_the_card_moves_to_answered(tmp_path):
    config = _product(tmp_path, PERSON)
    record_answer(config, "ADR-0003", "2", "Alex", date(2026, 10, 30))
    record = _records(config)["ADR-0003"]
    assert (record["status"], record["choice"], record["answered_by"]) == (
        "accepted",
        "password first",
        "Alex",
    )
    assert "proposed_because" not in record
    assert "Answered by you (1)" in render(config)


def test_an_answer_selecting_no_option_is_refused(tmp_path):
    config = _product(tmp_path, PERSON)
    with pytest.raises(ValueError, match="selects no option"):
        record_answer(config, "ADR-0003", "7", "Alex", date(2026, 10, 30))


def test_the_agent_s_decision_waits_for_no_answer(tmp_path):
    config = _product(tmp_path, AGENT)
    with pytest.raises(ValueError, match="waits for no answer"):
        record_answer(config, "ADR-0002", "1", "Alex", date(2026, 10, 30))


def test_the_command_prints_the_card_in_the_terminal(tmp_path, capsys):
    config = _product(tmp_path, PERSON)
    assert main(["--root", str(config.root), "--ask", "ADR-0003"]) == 0
    out = capsys.readouterr().out
    assert "Why you: A high requirement: who may sign in." in out
    assert "Your answer [Y / 1 / 2]:" in out
