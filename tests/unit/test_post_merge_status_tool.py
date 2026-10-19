"""tools/post_merge_status_tool.py — the crossing sign on the pull request: wait, or merge."""

import json

import pytest

from tools import post_merge_status_tool
from tools.post_merge_status_tool import CONTEXT, LIMIT, READY, RUNNING, main, sign


def _finding(gate, rule):
    return {"gate": gate, "rule": rule, "file": ".", "line": None, "message": "m"}


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
        "Wait: the reviewer agent's approval; a person's approval (sampled); "
        "gates red: check_stack_commands_gate",
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
