"""tools/post_merge_status_tool.py — the crossing sign on the pull request: wait, or merge."""

import json

import pytest

from tools import post_merge_status_tool
from tools.post_merge_status_tool import CONTEXT, LIMIT, READY, RUNNING, main, sign


def _finding(gate, rule, message="m"):
    return {"gate": gate, "rule": rule, "file": ".", "line": None, "message": message}


def test_green_gates_say_ready_to_merge():
    reported = [_finding("check_design_contract_gate", "MISSING_FIELD")]  # in progress only
    assert sign({"findings": [], "reported": reported}) == ("success", READY)


def test_the_sign_says_what_is_missing():
    state = {
        "findings": [
            _finding("verify_delivery_reviewed_gate", "MISSING_AGENT_REVIEW"),
            _finding("verify_delivery_reviewed_gate", "MISSING_PERSON_APPROVAL"),
            _finding("check_stack_commands_gate", "CHECK_FAILED"),
            _finding("check_stack_commands_gate", "SUITE_FAILED"),
            _finding("verify_delivery_reviewed_gate", "INCOMPLETE_CHECKLIST"),
        ]
    }
    assert sign(state) == (
        "failure",
        "Wait: the reviewer agent's approval; a person's review: approve on GitHub; "
        "gates red: check_stack_commands_gate",
    )


def test_a_head_sent_back_says_changes_requested_not_approval():
    """FB-55: "the reviewer agent's approval" is for a head not reviewed yet."""
    message = "o/r#36: the reviewer agent requested changes on its head 08672b4 (bot): fix"
    state = {
        "findings": [_finding("verify_delivery_reviewed_gate", "MISSING_AGENT_REVIEW", message)]
    }
    assert sign(state) == (
        "failure",
        "Wait: changes requested by the reviewer agent: fix the findings and push",
    )


def test_a_persons_review_names_who_why_and_what_to_do_once():
    """FB-43: "a person's review" named neither who nor why."""
    why = "acme/login#25 needs a person's review (why: it changes the quality gates' own files)"
    state = {
        "findings": [
            _finding("verify_delivery_reviewed_gate", "REVIEW_ITEMS_UNANSWERED"),
            _finding("verify_delivery_reviewed_gate", "MISSING_PERSON_APPROVAL", why),
            _finding("verify_delivery_reviewed_gate", "REVIEW_STORY_UNSOURCED"),
        ]
    }
    assert sign(state, ("alexxo",)) == (
        "failure",
        "Wait: the reviewer agent's approval; "
        "a review by alexxo (it changes the quality gates' own files): approve on GitHub",
    )
    ticks = {"findings": [_finding("verify_delivery_reviewed_gate", "REVIEW_ITEMS_UNANSWERED")]}
    assert sign(ticks, ("alexxo", "bob")) == (
        "failure",
        "Wait: a review by alexxo or bob: tick every item of its comment, then approve again",
    )


def test_gates_that_did_not_finish_say_wait():
    assert sign(None) == ("failure", "Wait: gates red: the gates did not finish")


def test_a_long_sign_is_cut_to_githubs_limit():
    gates = [f"check_gate_number_{n}_gate" for n in range(10)]
    _state, text = sign({"findings": [_finding(g, "X") for g in gates]})
    assert len(text) == LIMIT and text.endswith("…")


def test_the_sign_is_posted_on_the_head(tmp_path, monkeypatch):
    posted = []
    monkeypatch.setenv("QF_HOST_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/login")
    monkeypatch.setattr(post_merge_status_tool, "_post", lambda *a: posted.append(a[1:]))
    stage = tmp_path / "stage.json"
    stage.write_text(json.dumps({"findings": []}))
    assert main(["--sha", "abc1234", "--running"]) == 0
    assert main(["--sha", "abc1234", "--stage-file", str(stage)]) == 0
    assert main(["--sha", "abc1234", "--stage-file", str(tmp_path / "none.json")]) == 0
    assert posted == [
        ("acme/login", "abc1234", "pending", RUNNING),
        ("acme/login", "abc1234", "success", READY),
        ("acme/login", "abc1234", "failure", "Wait: gates red: the gates did not finish"),
    ]
    assert CONTEXT == "qf/merge"


def test_a_sign_that_cannot_be_posted_leaves_none(monkeypatch, capsys):
    """No sign means wait: a token that cannot write statuses fails no run."""
    import urllib.error

    def refuse(*_a):
        raise urllib.error.URLError("403")

    monkeypatch.setenv("QF_HOST_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/login")
    monkeypatch.setattr(post_merge_status_tool, "_post", refuse)
    assert main(["--sha", "abc1234", "--running"]) == 0
    assert "was not posted" in capsys.readouterr().err


def test_without_a_token_nothing_is_posted(monkeypatch):
    monkeypatch.delenv("QF_HOST_TOKEN", raising=False)
    assert main(["--sha", "abc1234", "--running"]) == 2


@pytest.mark.parametrize("args", [["--sha", "a"], ["--running"]])
def test_the_head_and_one_kind_of_sign_are_required(args):
    with pytest.raises(SystemExit):
        main(args)
