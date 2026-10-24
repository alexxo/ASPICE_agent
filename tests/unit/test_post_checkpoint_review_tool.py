"""tools/post_checkpoint_review_tool.py — the person's review in plain words."""

import json

import pytest
from product_builder import (
    AGENT,
    HOST_REPO,
    add_origin,
    build_product,
    git_head,
    note,
    pull_request,
    review,
    write_host,
)

from gates.sup.verify_delivery_reviewed_gate import person_review
from tools import post_checkpoint_review_tool
from tools.post_checkpoint_review_tool import MARK, answers, main, render
from tools.read_host_tool import FileHost
from tools.read_product_config_tool import read_product_config

ASKED = {
    "person": {"condition": 4, "reason": "publishes posts to the live site"},
    "findings": [
        {
            "finding": "the limit is 10, the requirement says 5",
            "outcome": "disputed",
            "author_answer": "5 locks out users on a typo",
            "reviewer_position": "the requirement says 5",
        }
    ],
}


@pytest.fixture
def product(tmp_path):
    root = build_product(tmp_path / "product")
    add_origin(root)
    return root


def _pull(product, tmp_path, record=ASKED, notes=()):
    head = git_head(product)
    data = pull_request(4, head, reviews=[review(AGENT, head, record=record)], notes=notes)
    path = write_host(tmp_path / "host.json", pulls=[data])
    return path, FileHost(path).pull_request(HOST_REPO, 4)


def _render(product, pull, record=ASKED):
    config = read_product_config(product)
    return render(config, HOST_REPO, pull, person_review(config, pull, record), record)


def test_the_review_says_why_and_mentions_the_people(product, tmp_path):
    _, pull = _pull(product, tmp_path)
    body = _render(product, pull)
    assert body.startswith(MARK)
    assert "@lead-bob" in body and "publishes posts to the live site" in body
    assert [title for title, _ in answers(body)] == [
        "1. Disagreement (disputed)",
        "2. The reviewer agent asks for a person",
    ]


def test_nothing_to_judge_needs_no_comment(product, tmp_path):
    record = {"person": "none", "findings": []}
    _, pull = _pull(product, tmp_path, record)
    assert _render(product, pull, record) is None


@pytest.mark.parametrize(
    ("boxes", "answer"),
    [("[x] yes\n- [ ] no", "yes"), ("[ ] yes\n- [x] no", "no"), ("[x] yes\n- [x] no", None)],
)
def test_the_first_box_alone_is_yes(boxes, answer):
    assert answers(f"### 1. An item\n\ntext\n\n- {boxes}\n") == [("1. An item", answer)]


@pytest.fixture
def posted(monkeypatch):
    monkeypatch.setenv("QF_HOST_TOKEN", "run-token")
    sent = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        sent.append(request)
        return Response()

    monkeypatch.setattr(post_checkpoint_review_tool.urllib.request, "urlopen", urlopen)
    return sent


def test_ci_posts_the_review_once_per_head_and_items(product, tmp_path, monkeypatch, posted):
    path, pull = _pull(product, tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(path))
    assert main(["--root", str(product), "--pull-request", "4"]) == 0
    (request,) = posted
    assert request.full_url.endswith(f"/repos/{HOST_REPO}/issues/4/comments")
    assert request.get_method() == "POST"
    body = json.loads(request.data)["body"]

    path, _ = _pull(product, tmp_path, notes=[note(body, "2026-10-24T09:00:00Z", id=77)])
    monkeypatch.setenv("QF_HOST_FILE", str(path))
    assert main(["--root", str(product), "--pull-request", "4"]) == 0
    assert len(posted) == 1  # already posted: an approval stays valid


def test_a_new_head_rewrites_the_one_comment(product, tmp_path, monkeypatch, posted):
    _, pull = _pull(product, tmp_path)
    older = _render(product, pull).replace(pull.head, "0" * 40)
    path, _ = _pull(product, tmp_path, notes=[note(older, "2026-10-24T09:00:00Z", id=77)])
    monkeypatch.setenv("QF_HOST_FILE", str(path))
    assert main(["--root", str(product), "--pull-request", "4"]) == 0
    (request,) = posted
    assert request.full_url.endswith(f"/repos/{HOST_REPO}/issues/comments/77")
    assert request.get_method() == "PATCH"


def test_without_the_reviewer_agents_record_nothing_is_posted(
    product, tmp_path, monkeypatch, posted
):
    path, _ = _pull(product, tmp_path, record=None)
    monkeypatch.setenv("QF_HOST_FILE", str(path))
    assert main(["--root", str(product), "--pull-request", "4"]) == 0
    assert posted == []
