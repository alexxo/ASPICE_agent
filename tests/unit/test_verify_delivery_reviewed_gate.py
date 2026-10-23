"""gates/sup/verify_delivery_reviewed_gate.py — every delivery reviewed, the sample by a person."""

import json
import subprocess

import pytest
from product_builder import (
    AGENT,
    AUTHOR,
    PERSON,
    add_origin,
    build_product,
    comment,
    commit_all,
    git_head,
    issue,
    pull_request,
    review,
    write_host,
)

from gates.sup.verify_delivery_reviewed_gate import check
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


def _on_main(product, message="docs: notes #3"):
    """A commit on main after the one that started the product."""
    subprocess.run(["git", "-C", str(product), "checkout", "-q", "main"], check=True)
    (product / "notes.md").write_text(message + "\n")
    commit_all(product, message)
    return git_head(product)


def _push(tmp_path, monkeypatch, before, after):
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "ref": "refs/heads/main",
                "before": before,
                "after": after,
                "repository": {"default_branch": "main"},
            }
        )
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))


def test_a_commit_on_main_without_merged_pull_request_is_caught(product, tmp_path, monkeypatch):
    head = _on_main(product)
    assert _rules(product, tmp_path, monkeypatch) == ["MERGED_WITHOUT_PULL_REQUEST"]
    final = "f" * 40
    merged = pull_request(1, final, merged=True, commits=[head], reviews=[review(AGENT, final)])
    assert _rules(product, tmp_path, monkeypatch, merged) == []


def test_the_commit_that_started_the_product_is_exempt(product, tmp_path, monkeypatch):
    subprocess.run(["git", "-C", str(product), "checkout", "-q", "main"], check=True)
    assert _rules(product, tmp_path, monkeypatch) == []


def test_every_commit_a_push_adds_is_checked(product, tmp_path, monkeypatch):
    subprocess.run(["git", "-C", str(product), "checkout", "-q", "main"], check=True)
    before = git_head(product)
    reviewed = _on_main(product, "docs: reviewed #1")
    _on_main(product, "docs: pushed straight to main #2")
    _push(tmp_path, monkeypatch, before, git_head(product))
    final = "f" * 40
    merged = pull_request(1, final, merged=True, commits=[reviewed], reviews=[review(AGENT, final)])
    assert _rules(product, tmp_path, monkeypatch, merged) == ["MERGED_WITHOUT_PULL_REQUEST"]


def test_a_pull_request_merged_with_red_gates_is_caught(product, tmp_path, monkeypatch):
    head = _on_main(product)
    final = "f" * 40
    merged = pull_request(1, final, merged=True, commits=[head], reviews=[review(AGENT, final)])
    host = write_host(tmp_path / "host.json", pulls=[merged], checks={final: ["lint"]})
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    rules = [f.rule for f in check(read_product_config(product))]
    assert rules == ["GATES_NOT_PASSED"]


MERGED_AT = "2026-10-19T05:32:16Z"


def _red_merge(product, tmp_path, monkeypatch, checks, issues=()):
    head = _on_main(product)
    final = "f" * 40
    merged = pull_request(
        6, final, merged=True, merged_at=MERGED_AT, commits=[head], reviews=[review(AGENT, final)]
    )
    host = write_host(tmp_path / "host.json", pulls=[merged], checks={final: checks}, issues=issues)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return sorted(f.rule for f in check(read_product_config(product)))


@pytest.mark.parametrize(
    ("finished", "rules"),
    [("2026-10-19T05:30:00Z", []), ("2026-10-19T05:40:00Z", ["GATES_NOT_PASSED"])],
)
def test_only_gates_passed_before_the_merge_count(product, tmp_path, monkeypatch, finished, rules):
    """A re-run after the merge reads an empty range, so it proves nothing (FB-29)."""
    checks = [{"name": "gates", "completed_at": finished}]
    assert _red_merge(product, tmp_path, monkeypatch, checks) == rules


@pytest.mark.parametrize(
    ("by", "rules"),
    [(PERSON, []), (AUTHOR, ["GATES_NOT_PASSED"]), (AGENT, ["GATES_NOT_PASSED"])],
)
def test_an_urgent_approver_accepts_a_red_merge_after_the_fact(
    product, tmp_path, monkeypatch, by, rules
):
    """Only a person in urgent_approvers, never the author or an agent, clears it."""
    accepted = issue(
        9,
        "non-conformance",
        {"found_in": 6, "fixed_by": 7},
        comments=[comment(by, "/accept-delivery")],
    )
    assert _red_merge(product, tmp_path, monkeypatch, ["lint"], [accepted]) == rules


def test_a_direct_push_is_accepted_by_its_commit(product, tmp_path, monkeypatch):
    head = _on_main(product)
    accepted = issue(
        9, "non-conformance", {"commit": head[:7]}, comments=[comment(PERSON, "/accept-delivery")]
    )
    host = write_host(tmp_path / "host.json", issues=[accepted])
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    assert check(read_product_config(product)) == []


def test_a_merge_without_its_review_is_caught_on_main(product, tmp_path, monkeypatch):
    head = _on_main(product)
    final = "f" * 40
    merged = pull_request(1, final, merged=True, commits=[head])
    assert _rules(product, tmp_path, monkeypatch, merged) == ["MISSING_AGENT_REVIEW"]


@pytest.mark.parametrize(
    "guarded", [".github/workflows/quality_gates.yml", ".framework", ".gitmodules", "qf.yaml"]
)
def test_a_change_to_the_gates_own_files_needs_a_person(product, tmp_path, monkeypatch, guarded):
    head = git_head(product)
    pull = pull_request(2, head, files=[guarded], reviews=[review(AGENT, head)])
    assert _rules(product, tmp_path, monkeypatch, pull) == ["MISSING_PERSON_APPROVAL"]


def test_a_proposed_release_checks_main_since_the_last_release(product, tmp_path, monkeypatch):
    _on_main(product, "docs: pushed straight to main #2")
    subprocess.run(
        ["git", "-C", str(product), "checkout", "-q", "-b", "release/v1.0.0"], check=True
    )
    (product / "releases").mkdir()
    (product / "releases" / "1.0.0.yaml").write_text("version: 1.0.0\n")
    commit_all(product, "chore(release): 1.0.0 #4")
    head = git_head(product)
    pull = pull_request(4, head, branch="release/v1.0.0", reviews=[review(AGENT, head)])
    assert _rules(product, tmp_path, monkeypatch, pull) == ["MERGED_WITHOUT_PULL_REQUEST"]


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


DOCUMENTS = ["docs/requirements/login.md", "docs/diagrams/login.sequence.json"]
WITHOUT_LOGGING = ("correctness", "style", "traceability")


def test_a_change_without_code_is_reviewed_without_logging(product, tmp_path, monkeypatch):
    head = git_head(product)
    agent = review(AGENT, head, items=WITHOUT_LOGGING)
    pull = pull_request(1, head, files=DOCUMENTS, reviews=[agent])
    assert _rules(product, tmp_path, monkeypatch, pull) == []


def test_a_change_with_code_is_reviewed_for_logging(product, tmp_path, monkeypatch):
    head = git_head(product)
    pull = pull_request(1, head, reviews=[review(AGENT, head, items=WITHOUT_LOGGING)])
    assert _rules(product, tmp_path, monkeypatch, pull) == ["INCOMPLETE_CHECKLIST"]


def test_a_missing_review_names_the_reviewer_session(product, tmp_path, monkeypatch):
    pull = pull_request(1, git_head(product))
    monkeypatch.setenv("QF_HOST_FILE", str(write_host(tmp_path / "host.json", pulls=[pull])))
    (finding,) = check(read_product_config(product))
    assert "agent/run_reviewer_agent.md" in finding.message


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
