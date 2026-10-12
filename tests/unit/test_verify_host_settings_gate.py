"""gates/sup/verify_host_settings_gate.py — every delivery reviewed, the sample by a person."""

import subprocess

import pytest
from product_builder import (
    AGENT,
    AUTHOR,
    PERSON,
    add_origin,
    build_product,
    git_head,
    pull_request,
    review,
    write_host,
)

from gates.sup.verify_host_settings_gate import check
from tools.read_product_config_tool import read_product_config

BRANCH = "feature/REQ-0047-lockout"


@pytest.fixture
def product(tmp_path):
    root = build_product(tmp_path / "product")
    subprocess.run(["git", "-C", str(root), "branch", "-M", "main"], check=True)
    subprocess.run(["git", "-C", str(root), "checkout", "-q", "-b", BRANCH], check=True)
    add_origin(root)
    return root


def _rules(product, tmp_path, monkeypatch, *pulls):
    monkeypatch.setenv("QF_HOST_FILE", str(write_host(tmp_path / "host.json", pulls=pulls)))
    return sorted(f.rule for f in check(read_product_config(product)))


def test_a_reviewed_pull_request_passes(product, tmp_path, monkeypatch):
    head = git_head(product)
    pull = pull_request(1, head, reviews=[review(AGENT, head)])
    assert _rules(product, tmp_path, monkeypatch, pull) == []


def test_a_branch_without_pull_request_is_not_delivered(product, tmp_path, monkeypatch):
    assert _rules(product, tmp_path, monkeypatch) == ["NO_PULL_REQUEST"]


def test_a_commit_on_main_without_merged_pull_request_is_caught(product, tmp_path, monkeypatch):
    subprocess.run(["git", "-C", str(product), "checkout", "-q", "main"], check=True)
    assert _rules(product, tmp_path, monkeypatch) == ["MERGED_WITHOUT_PULL_REQUEST"]
    head = git_head(product)
    final = "f" * 40
    merged = pull_request(1, final, merged=True, commits=[head], reviews=[review(AGENT, final)])
    assert _rules(product, tmp_path, monkeypatch, merged) == []


@pytest.mark.parametrize(
    "reviews",
    [
        [],
        [("someone-else", "APPROVED")],  # not a declared agent
        [(AGENT, "CHANGES_REQUESTED")],
        [(AGENT, "APPROVED"), (AGENT, "CHANGES_REQUESTED")],  # the latest decision counts
    ],
)
def test_without_the_agents_approval_the_review_is_missing(product, tmp_path, monkeypatch, reviews):
    head = git_head(product)
    pull = pull_request(1, head, reviews=[review(a, head, s) for a, s in reviews])
    assert "MISSING_AGENT_REVIEW" in _rules(product, tmp_path, monkeypatch, pull)


def test_an_approval_of_an_older_head_does_not_count(product, tmp_path, monkeypatch):
    pull = pull_request(1, git_head(product), reviews=[review(AGENT, "0" * 40)])
    assert _rules(product, tmp_path, monkeypatch, pull) == ["MISSING_AGENT_REVIEW"]


def test_the_author_never_reviews_their_own_work(product, tmp_path, monkeypatch):
    head = git_head(product)
    pull = pull_request(1, head, author=AGENT, reviews=[review(AGENT, head)])
    assert _rules(product, tmp_path, monkeypatch, pull) == ["MISSING_AGENT_REVIEW"]


def test_an_approval_with_an_unchecked_item_is_incomplete(product, tmp_path, monkeypatch):
    head = git_head(product)
    pull = pull_request(1, head, reviews=[review(AGENT, head, failing=["traceability"])])
    assert _rules(product, tmp_path, monkeypatch, pull) == ["INCOMPLETE_CHECKLIST"]


def test_a_sampled_pull_request_waits_for_a_person(product, tmp_path, monkeypatch):
    head = git_head(product)
    agent = review(AGENT, head)
    sampled = pull_request(5, head, reviews=[agent])  # 5 is a multiple of sample_every
    assert _rules(product, tmp_path, monkeypatch, sampled) == ["MISSING_PERSON_APPROVAL"]
    approved = pull_request(5, head, reviews=[agent, review(PERSON, head)])
    assert _rules(product, tmp_path, monkeypatch, approved) == []


def test_an_architecture_pull_request_always_needs_a_person(product, tmp_path, monkeypatch):
    head = git_head(product)
    files = ["docs/architecture/architecture.md"]
    pull = pull_request(2, head, files=files, reviews=[review(AGENT, head)])
    assert _rules(product, tmp_path, monkeypatch, pull) == ["MISSING_PERSON_APPROVAL"]


@pytest.mark.parametrize(
    "person",
    [
        review(AUTHOR, "HEAD"),  # the author
        review("ci[bot]", "HEAD", bot=True),  # a bot
        review(PERSON, "0" * 40),  # an older head
    ],
)
def test_only_a_person_on_the_current_head_counts(product, tmp_path, monkeypatch, person):
    head = git_head(product)
    person = {**person, "commit": head if person["commit"] == "HEAD" else person["commit"]}
    pull = pull_request(5, head, reviews=[review(AGENT, head), person])
    assert _rules(product, tmp_path, monkeypatch, pull) == ["MISSING_PERSON_APPROVAL"]
