"""agent/record_answer_tool.py — unclear criteria checked and answered before checkpoint 2."""

import pytest
from product_builder import check_criteria, commit_all, render_reviews

from agent.record_answer_tool import (
    label,
    main,
    open_questions,
    question_findings,
    read_questions,
    record_answer,
    summary,
)
from agent.record_checkpoint_tool import record_checkpoint
from agent.render_review_tool import render, render_review
from gates.swe.verify_requirements_approval_gate import check
from tools.read_product_config_tool import read_product_config

LOCK = {
    "about": {"requirement": "REQ-0012", "criterion": 2},
    "question": "When is the account locked?",
    "readings": [
        {"reading": "locked at the 3rd failure", "example": "✗ ✗ ✗ → locked"},
        {
            "reading": "locked at the 4th attempt, after 3 failures",
            "example": "✗ ✗ ✗ → 4th refused, locked",
            "conflicts": "REQ-0013 criterion 1",
        },
    ],
    "proposal": {"choice": 1, "source": 'diagram message "3rd failure → lock"'},
}
TERM = {
    "about": {"term": "account"},
    "question": "Is a closed account still an account?",
    "readings": [
        {"reading": "yes", "example": "closed → listed"},
        {"reading": "no", "example": "closed → gone"},
    ],
    "proposal": "none",
}


def _config(root):
    return read_product_config(root)


def _rules(root):
    return sorted(f.rule for f in check(_config(root)))


def _login(root):
    return root / "docs/requirements/login.md"


def _rewrite(root, uid="REQ-0011"):
    """The error criterion (2) of a requirement, rewritten."""
    path = _login(root)
    text = path.read_text()
    at = text.index("it reports it", text.index(f"uid: {uid}"))
    path.write_text(text[:at] + "it reports the failure" + text[at + len("it reports it") :])


@pytest.fixture
def asked(product):
    """The check found the lock criterion unclear; the page shows the question."""
    check_criteria(product, [LOCK])
    render_review(product)
    return product


def test_a_product_never_checked_lists_every_criterion_and_term(product, capsys):
    (product / "docs/requirements/questions.yaml").unlink()
    assert main(["--unchecked", "--root", str(product)]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed[0] == "REQ-0011 criterion 1"
    assert "term account" in printed
    assert [f.rule for f in question_findings(_config(product))] == ["CRITERIA_NOT_CHECKED"]


def test_a_question_is_numbered_and_bound_to_its_criterion(asked):
    (question,) = read_questions(_config(asked))["questions"]
    assert question["id"] == "Q1"
    assert len(question["asked"]) == 64
    assert _rules(asked) == []  # it waits for the person at checkpoint 2, not for the agent


def test_an_open_question_is_reported_once_design_work_exists(asked):
    design = asked / "docs/architecture/auth-flow.md"
    design.parent.mkdir(parents=True, exist_ok=True)
    design.write_text("# The components\n")
    assert "QUESTION_UNANSWERED" in _rules(asked)


def test_an_open_question_sits_in_its_requirements_row_with_its_options(asked):
    page = render(_config(asked))
    assert "1 question(s) to settle before you approve:" in page
    row = page[page.index('id="Q1"') : page.index("</tr>", page.index('id="Q1"'))]
    assert "Q1 · REQ-0012 criterion 2:</b> When is the account locked?" in row
    assert "<li>neither: the requirement goes back to be rewritten</li>" in row
    assert "conflicts with REQ-0013 criterion 1" in row
    assert "Proposed: 1 — diagram message" in row


def test_an_approval_waits_for_every_answer(asked):
    with pytest.raises(ValueError, match="Q1 about REQ-0012 criterion 2 is not answered"):
        record_checkpoint(asked, 2, "approved", "Alex", "architect")


def test_an_answer_records_whether_it_took_the_proposal(asked):
    record_answer(asked, "Q1", 2, "Alex", "architect")
    (question,) = read_questions(_config(asked))["questions"]
    assert question["answer"] == {
        "choice": 2,
        "approver": {"name": "Alex", "role": "architect"},
        "proposal": "changed",
    }
    render_review(asked)
    assert "✓ Q1 · REQ-0012 criterion 2 settled: 2 — locked at the 4th attempt" in render(
        _config(asked)
    )
    assert "proposal changed, Alex" in render(_config(asked))
    assert _rules(asked) == []
    record_checkpoint(asked, 2, "approved", "Alex", "architect")


def test_without_a_proposal_the_answer_says_so(product):
    check_criteria(product, [TERM])
    record_answer(product, "Q1", 1, "Alex", "architect")
    assert read_questions(_config(product))["questions"][0]["answer"]["proposal"] == "none"


@pytest.mark.parametrize("choice", [0, 4])
def test_only_a_listed_number_is_an_answer(asked, choice):
    with pytest.raises(ValueError, match="choose 1 to 3"):
        record_answer(asked, "Q1", choice, "Alex", "architect")


def test_a_question_is_answered_once(asked):
    record_answer(asked, "Q1", 1, "Alex", "architect")
    with pytest.raises(ValueError, match="Q1 is not open"):
        record_answer(asked, "Q1", 2, "Alex", "architect")


def test_neither_holds_until_the_criterion_is_rewritten_and_checked_again(asked):
    record_answer(asked, "Q1", 3, "Alex", "architect")
    assert _rules(asked) == ["QUESTION_UNANSWERED", "REVIEW_PAGE_OUTDATED"]
    _rewrite(asked, "REQ-0012")
    render_review(asked)
    (finding,) = question_findings(_config(asked))
    assert finding.rule == "CRITERIA_NOT_CHECKED"
    assert "REQ-0012 criterion 2." in finding.message  # the rewritten one alone
    render_reviews(asked)
    assert _rules(asked) == []


def test_an_unanswered_question_whose_criterion_changed_is_gone(asked):
    _rewrite(asked, "REQ-0012")
    assert open_questions(_config(asked)) == []
    assert "Q1" not in render(_config(asked))


def test_a_criterion_left_unchanged_is_not_asked_again(product, capsys):
    _rewrite(product)
    assert main(["--unchecked", "--root", str(product)]) == 0
    assert capsys.readouterr().out.splitlines() == ["REQ-0011 criterion 2"]


def test_questions_are_numbered_as_the_page_shows_them(product):
    """FB-58: the numbers follow the page, top to bottom, not the session's order."""
    check_criteria(product, [TERM, LOCK])  # the glossary sits below the requirements
    numbered = {q["id"]: label(q["about"]) for q in read_questions(_config(product))["questions"]}
    assert numbered == {"Q1": "REQ-0012 criterion 2", "Q2": "term account"}


def test_a_criterion_unchanged_since_the_approval_is_not_checked_again(asked, capsys):
    """FB-59: a change request checks what it changed, not every criterion."""
    record_answer(asked, "Q1", 1, "Alex", "architect")
    render_review(asked)
    commit_all(asked, "Q1 answered")
    record_checkpoint(asked, 2, "approved", "Alex", "architect")
    commit_all(asked, "checkpoint 2 approved")
    (asked / "docs/requirements/questions.yaml").unlink()  # approved before the check existed
    _rewrite(asked)
    assert main(["--unchecked", "--root", str(asked)]) == 0
    assert capsys.readouterr().out.splitlines() == ["REQ-0011 criterion 2"]


def test_a_criterion_rewritten_to_settle_a_question_names_it(asked, capsys):
    """FB-59: the recheck asks only about the wording the rewrite added."""
    record_answer(asked, "Q1", 1, "Alex", "architect")
    _rewrite(asked, "REQ-0012")
    assert main(["--unchecked", "--root", str(asked)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "REQ-0012 criterion 2 — rewritten to settle Q1 (locked at the 3rd failure): ask only "
        "about wording the rewrite added"
    ]


def test_what_was_accepted_is_told_in_plain_words_the_risky_first(product):
    """Alex: a batch of proposals accepted with one Y is told back, risky ones first."""
    convention = {**TERM, "proposal": {"choice": 1, "source": "convention: closed is listed"}}
    check_criteria(product, [LOCK, convention])
    record_answer(product, "Q1", 1, "Alex", "architect")
    record_answer(product, "Q2", 1, "Alex", "architect")
    lines = summary(_config(product))
    assert lines[0] == (
        "⚠ Q1 · REQ-0012 criterion 2: the product will — locked at the 3rd failure "
        "(e.g. ✗ ✗ ✗ → locked)\n    Risky: a requirement of high criticality."
    )
    assert lines[1].startswith("⚠ Q2 · term account: the product will — yes")
    assert "it changes every requirement using the term" in lines[1]
    assert "decided by common practice, not by anything you approved" in lines[1]


def test_a_plain_answer_is_not_marked_risky(product):
    path = _login(product)
    text = path.read_text()
    at = text.index("criticality: high", text.index("uid: REQ-0012"))
    path.write_text(text[:at] + "criticality: low" + text[at + len("criticality: high") :])
    check_criteria(product, [LOCK])
    record_answer(product, "Q1", 1, "Alex", "architect")
    assert summary(_config(product)) == [
        "Q1 · REQ-0012 criterion 2: the product will — locked at the 3rd failure "
        "(e.g. ✗ ✗ ✗ → locked)"
    ]


def test_an_answer_can_be_given_again_until_the_criterion_is_rewritten(asked):
    record_answer(asked, "Q1", 1, "Alex", "architect")
    record_answer(asked, "Q1", 2, "Alex", "architect", again=True)
    assert read_questions(_config(asked))["questions"][0]["answer"]["choice"] == 2
    _rewrite(asked, "REQ-0012")
    assert summary(_config(asked)) == []
    with pytest.raises(ValueError, match="Q1 has no answer to change"):
        record_answer(asked, "Q1", 1, "Alex", "architect", again=True)


def test_a_question_about_something_that_does_not_exist_is_refused(product):
    with pytest.raises(ValueError, match="REQ-0999 criterion 1: no such"):
        check_criteria(product, [{**LOCK, "about": {"requirement": "REQ-0999", "criterion": 1}}])


def test_a_proposal_must_be_one_of_the_readings(product):
    with pytest.raises(ValueError, match="Q1: the proposal is not one of its readings"):
        check_criteria(product, [{**LOCK, "proposal": {"choice": 3, "source": "a guess"}}])


def test_questions_settled_before_the_previous_approval_are_not_shown_again(asked):
    record_answer(asked, "Q1", 1, "Alex", "architect")
    render_review(asked)
    commit_all(asked, "Q1 answered")
    record_checkpoint(asked, 2, "approved", "Alex", "architect")
    commit_all(asked, "checkpoint 2 approved")
    _rewrite(asked)
    render_reviews(asked)
    page = render(_config(asked))
    assert "Q1" not in page
    assert "question(s)" not in page


def test_one_rule_is_one_question_that_settles_each_criterion_it_names(product, capsys):
    """FB-60: the same convention is asked once, not once per criterion."""
    check_criteria(product, [{**LOCK, "also": [{"requirement": "REQ-0011", "criterion": 2}]}])
    record_answer(product, "Q1", 1, "Alex", "architect")
    assert summary(_config(product))[0].startswith("⚠ Q1 · REQ-0012 criterion 2 and 1 more:")
    _rewrite(product)
    assert main(["--unchecked", "--root", str(product)]) == 0
    assert capsys.readouterr().out.startswith("REQ-0011 criterion 2 — rewritten to settle Q1")


def test_a_rule_naming_a_criterion_that_does_not_exist_is_refused(product):
    with pytest.raises(ValueError, match="REQ-0999 criterion 1: no such"):
        check_criteria(product, [{**LOCK, "also": [{"requirement": "REQ-0999", "criterion": 1}]}])


def test_a_criterion_is_checked_again_once_after_its_rewrite(asked, capsys):
    """FB-60: the check, one recheck of the rewrite, and no third round."""
    record_answer(asked, "Q1", 1, "Alex", "architect")
    _rewrite(asked, "REQ-0012")
    check_criteria(asked, [{**LOCK, "question": "Is a refused sign-in a failure?"}])
    record_answer(asked, "Q2", 1, "Alex", "architect")
    path = _login(asked)
    path.write_text(path.read_text().replace("it reports the failure", "it reports the sign-in"))
    assert main(["--unchecked", "--root", str(asked)]) == 0
    assert capsys.readouterr().out == ""
    assert [f.rule for f in question_findings(_config(asked))] == []
