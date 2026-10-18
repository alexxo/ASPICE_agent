"""tools/post_review_tool.py — the reviewer agent's review, with the checklist in its fixed form."""

import json

import pytest
from product_builder import AUTHOR, add_origin, build_product

from tools import post_review_tool
from tools.post_review_tool import CHECKLIST, checklist, main, render, required_items
from tools.read_host_tool import GitHubHost
from tools.read_product_config_tool import read_product_config

WITHOUT_LOGGING = ("correctness", "style", "traceability")


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


@pytest.mark.parametrize(
    ("files", "items"),
    [
        (["src/auth_service/lockout.py", "docs/requirements/login.md"], CHECKLIST),
        (["docs/requirements/login.md", "docs/diagrams/login.sequence.json"], WITHOUT_LOGGING),
        (["source.md"], WITHOUT_LOGGING),  # a name that only starts like the code folder
    ],
)
def test_logging_is_asked_only_of_a_change_with_code(tmp_path, files, items):
    config = read_product_config(build_product(tmp_path / "product", git=False))
    assert required_items(config, files) == items


def test_the_checklist_holds_the_items_asked_for():
    assert checklist(render(set(), items=WITHOUT_LOGGING)) == dict.fromkeys(WITHOUT_LOGGING, True)


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


def _host(monkeypatch, files):
    pull = {"user": {"login": AUTHOR}, "head": {"sha": "h2"}, "merged": False}
    changed = [{"filename": f} for f in files]

    def get(self, path):
        if path.endswith("/pulls/4"):
            return pull
        return changed if "/pulls/4/files" in path else []

    monkeypatch.setattr(GitHubHost, "_get", get)


@pytest.fixture
def reviewed(tmp_path, monkeypatch):
    root = build_product(tmp_path / "product")
    add_origin(root)
    monkeypatch.setenv("QF_HOST_TOKEN", "reviewer-token")
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
    return root, sent


@pytest.mark.parametrize(
    ("files", "items"),
    [
        (["src/auth_service/lockout.py"], CHECKLIST),
        (["docs/requirements/login.md"], WITHOUT_LOGGING),
    ],
)
def test_the_review_is_posted_on_the_current_head(reviewed, monkeypatch, files, items):
    root, sent = reviewed
    _host(monkeypatch, files)
    assert main(["--root", str(root), "--pull-request", "4", "--decision", "approve"]) == 0
    (request,) = sent
    assert request.full_url.endswith("/repos/acme/login/pulls/4/reviews")
    assert request.get_header("Authorization") == "Bearer reviewer-token"
    payload = json.loads(request.data)
    assert (payload["commit_id"], payload["event"]) == ("h2", "APPROVE")
    assert checklist(payload["body"]) == dict.fromkeys(items, True)


def test_an_item_not_asked_for_cannot_fail(reviewed, monkeypatch, tmp_path, capsys):
    root, sent = reviewed
    _host(monkeypatch, ["docs/requirements/login.md"])
    findings = tmp_path / "findings.md"
    findings.write_text("No end event.")
    args = ["--root", str(root), "--pull-request", "4", "--decision", "request_changes"]
    assert main([*args, "--failing", "logging", "--findings", str(findings)]) == 2
    assert "changes no code" in capsys.readouterr().err
    assert sent == []
