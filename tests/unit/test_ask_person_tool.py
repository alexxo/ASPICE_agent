"""agent/ask_person_tool.py — every decision put to a person, in one plain pattern."""

import pytest
import yaml

from agent.ask_person_tool import check, main, render, reply

PASSWORD = {
    "question": "What happens when the user enters a wrong password?",
    "options": "We could block the account immediately, or give the user two more chances.",
    "select": ["block immediately", "give two more chances"],
    "proposal": {"choice": 2, "why": "the sign-in diagram shows three attempts"},
}


def test_the_terminal_shows_question_options_select_and_proposal():
    assert render(check(PASSWORD)).splitlines() == [
        "Question: What happens when the user enters a wrong password?",
        "Options: We could block the account immediately, or give the user two more chances.",
        "Select your option: 1. block immediately, 2. give two more chances",
        "Proposed: 2. give two more chances — the sign-in diagram shows three attempts.",
        "Your answer [Y / 1 / 2]:",
    ]


def test_the_code_host_gets_a_box_per_option():
    text = render(PASSWORD, markdown=True)
    assert "**Select your option:**\n- [ ] 1. block immediately\n- [ ] 2. give two" in text
    assert text.endswith(
        "**Proposed:** 2. give two more chances — the sign-in diagram shows three attempts."
    )


@pytest.mark.parametrize(("typed", "selected"), [("Y", 2), ("y", 2), ("1", 1), (" 2 ", 2)])
def test_a_listed_number_or_y_selects(typed, selected):
    assert reply(PASSWORD, typed) == selected


@pytest.mark.parametrize("typed", ["3", "0", "yes", "block", ""])
def test_anything_else_selects_nothing(typed):
    assert reply(PASSWORD, typed) is None


def test_without_a_proposal_y_is_not_an_answer():
    plain = {k: v for k, v in PASSWORD.items() if k != "proposal"}
    assert reply(plain, "Y") is None
    assert render(plain).endswith("Your answer [1 / 2]:")


def test_a_proposal_must_be_one_of_the_options():
    with pytest.raises(ValueError, match="the proposal is not one of the options"):
        check({**PASSWORD, "proposal": {"choice": 3, "why": "a guess"}})


def test_a_requirement_id_is_refused():
    with pytest.raises(ValueError, match="not a valid choice.v1 at 'question'"):
        check({**PASSWORD, "question": "Is REQ-0012 right?"})


def test_the_command_line_asks_again_on_a_wrong_answer(tmp_path, capsys):
    path = tmp_path / "choice.yaml"
    path.write_text(yaml.safe_dump(PASSWORD))
    assert main(["--file", str(path), "--answer", "Y"]) == 0
    assert capsys.readouterr().out == "2\n"
    assert main(["--file", str(path), "--answer", "maybe"]) == 1
    assert "selects no option: answer Y or 1 to 2" in capsys.readouterr().err
