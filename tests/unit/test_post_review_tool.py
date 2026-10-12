"""tools/post_review_tool.py — the reviewer agent's review, with the checklist in its fixed form."""

import json
import subprocess

import pytest
from product_builder import AUTHOR, commit_all

from tools import post_review_tool
from tools.post_review_tool import CHECKLIST, checklist, main, render
from tools.read_host_tool import GitHubHost


def test_the_checklist_reads_back_what_was_rendered():
    assert checklist(render(set())) == {item: True for item in CHECKLIST}
    assert checklist(render({"logging"}, "No end event in lockout.py:12.")) == {
        "correctness": True,
        "style": True,
        "traceability": True,
        "logging": False,
    }


def test_a_body_without_the_checklist_has_none():
    assert checklist("LGTM") is None


def test_text_after_the_checklist_is_not_read_as_an_item():
    body = render(set(), "Findings:\n- [ ] logging is fine")
    assert checklist(body) == {item: True for item in CHECKLIST}


def test_an_approval_with_a_failing_item_is_refused():
    with pytest.raises(SystemExit) as exit_:
        main(["--pull-request", "1", "--decision", "approve", "--failing", "style"])
    assert exit_.value.code == 2


def test_a_request_for_changes_needs_the_items_and_the_findings():
    with pytest.raises(SystemExit):
        main(["--pull-request", "1", "--decision", "request_changes"])


def test_without_its_own_token_the_reviewer_posts_nothing(capsys):
    assert main(["--pull-request", "1", "--decision", "approve"]) == 2
    assert "QF_HOST_TOKEN" in capsys.readouterr().err


def test_the_review_is_posted_on_the_current_head(tmp_path, monkeypatch):
    root = tmp_path / "product"
    root.mkdir()
    commit_all(root, "start")
    remote = ["git", "-C", str(root), "remote", "add", "origin"]
    subprocess.run([*remote, "https://github.com/acme/login.git"], check=True)
    monkeypatch.setenv("QF_HOST_TOKEN", "reviewer-token")
    pull = {"user": {"login": AUTHOR}, "head": {"sha": "h2"}, "merged": False}
    monkeypatch.setattr(
        GitHubHost, "_get", lambda self, path: pull if path.endswith("/pulls/4") else []
    )
    sent = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        sent.append(request)
        return Response()

    monkeypatch.setattr(post_review_tool.urllib.request, "urlopen", urlopen)
    assert main(["--root", str(root), "--pull-request", "4", "--decision", "approve"]) == 0
    (request,) = sent
    assert request.full_url.endswith("/repos/acme/login/pulls/4/reviews")
    assert request.get_header("Authorization") == "Bearer reviewer-token"
    payload = json.loads(request.data)
    assert (payload["commit_id"], payload["event"]) == ("h2", "APPROVE")
    assert checklist(payload["body"]) == {item: True for item in CHECKLIST}
