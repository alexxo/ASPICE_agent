"""agent/record_checkpoint_tool.py — merges a checkpoint's pull request once the
architect approved it on the code host; the merge is the record (v4.0.0)."""

import pytest
from product_builder import (
    AGENT,
    AUTHOR,
    HOST_REPO,
    PERSON,
    add_origin,
    approve_checkpoint,
    commit_all,
    git_head,
    pull_request,
    review,
    write_host,
)

from agent.record_checkpoint_tool import (
    ChangesRequested,
    Checkpoint,
    Waiting,
    current_approval,
    main,
)
from tools.post_merge_status_tool import READY
from tools.read_approvals_tool import subject_files
from tools.read_host_tool import FileHost
from tools.read_product_config_tool import read_product_config

ARCHITECT = PERSON  # qf.yaml review.architect of the built product


def test_requirements_subject_is_the_requirements_their_page_and_their_diagrams(product):
    files = subject_files(read_product_config(product), "requirements")
    assert [f.relative_to(product).as_posix() for f in files] == [
        "docs/diagrams/auth-flow.architecture.json",
        "docs/diagrams/auth-flow.wishes.yaml",
        "docs/diagrams/login.invariants.yaml",
        "docs/diagrams/login.sequence.json",
        "docs/diagrams/login.wishes.yaml",
        "docs/glossary.md",
        "docs/requirements/login.md",
        "docs/requirements/questions.yaml",
        "docs/requirements/review.html",
    ]


def test_diagrams_subject_is_the_specs_invariants_pictures_and_page(product):
    files = subject_files(read_product_config(product), "diagrams")
    assert [f.name for f in files] == [
        "auth-flow.architecture.html",
        "auth-flow.architecture.json",
        "auth-flow.wishes.yaml",
        "login.invariants.yaml",
        "login.sequence.html",
        "login.sequence.json",
        "login.wishes.yaml",
        "review.html",
    ]


def _checkpoint(tmp_path, product, *reviews, checkpoint=2, sign=READY, **pull):
    """The checkpoint's pull request #7 at the product's head, its merges recorded."""
    add_origin(product)
    head = pull.pop("head", git_head(product))
    branch = pull.pop("branch", f"checkpoint/{checkpoint}")
    found = pull_request(7, head, branch=branch, reviews=reviews, **pull)
    host = write_host(tmp_path / "host.json", pulls=[found], signs={head: sign} if sign else {})
    merged = []
    step = Checkpoint(
        product, checkpoint, 7, host=FileHost(host), merge=lambda *a: merged.append(a)
    )
    return step, merged, host


def test_the_architects_approval_and_a_ready_sign_merge_the_head(product, tmp_path):
    head = git_head(product)
    step, merged, _ = _checkpoint(tmp_path, product, review(ARCHITECT, head))
    assert step.decide() == head
    assert merged == [(HOST_REPO, 7, head)]


def test_no_decision_of_the_architect_waits(product, tmp_path):
    """The agent's, the author's and another person's reviews decide nothing."""
    head = git_head(product)
    reviews = (review(AGENT, head), review(AUTHOR, head), review("lead-eve", head))
    step, merged, _ = _checkpoint(tmp_path, product, *reviews)
    with pytest.raises(Waiting, match=f"{ARCHITECT}'s review of the head of #7"):
        step.decide()
    assert merged == []


def test_an_approval_of_an_older_head_waits(product, tmp_path):
    step, merged, _ = _checkpoint(tmp_path, product, review(ARCHITECT, "0" * 40))
    with pytest.raises(Waiting):
        step.decide()
    assert merged == []


def test_a_request_for_changes_gives_its_reason(product, tmp_path, monkeypatch):
    head = git_head(product)
    step, merged, host = _checkpoint(
        tmp_path, product, review(ARCHITECT, head), review(ARCHITECT, head, "CHANGES_REQUESTED")
    )
    with pytest.raises(ChangesRequested, match="Looks right."):
        step.decide()
    assert merged == []
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    assert main(["--root", str(product), "--checkpoint", "2", "--pull-request", "7"]) == 4


def test_an_approved_head_waits_for_the_crossing_sign(product, tmp_path):
    head = git_head(product)
    step, merged, _ = _checkpoint(
        tmp_path, product, review(ARCHITECT, head), sign="Wait: gates running"
    )
    with pytest.raises(Waiting, match="crossing sign"):
        step.decide()
    assert merged == []


def test_only_a_pull_request_from_the_checkpoints_branch_is_merged(product, tmp_path):
    head = git_head(product)
    step, merged, _ = _checkpoint(tmp_path, product, review(ARCHITECT, head), branch="docs/req")
    with pytest.raises(ValueError, match="branch checkpoint/2"):
        step.decide()
    assert merged == []


def test_what_is_merged_is_what_is_checked(product, tmp_path):
    step, merged, _ = _checkpoint(tmp_path, product, review(ARCHITECT, "1" * 40), head="1" * 40)
    with pytest.raises(ValueError, match="not at the approved head"):
        step.decide()
    assert merged == []


def test_an_approval_of_a_stale_review_page_is_never_merged(product, tmp_path):
    """The person approves the requirements they saw (§ 5 stages 1 and 2, rule 24)."""
    login = product / "docs/requirements/login.md"
    login.write_text(login.read_text().replace("Five failed", "Three failed"))
    commit_all(product, "docs: three failed sign-ins REQ-0011")
    step, merged, _ = _checkpoint(tmp_path, product, review(ARCHITECT, git_head(product)))
    with pytest.raises(ValueError, match="not what the files render now"):
        step.decide()
    assert merged == []


def test_seal_4_is_no_checkpoint_pull_request(product, tmp_path):
    """A person's approval of a feature's pull request is CI's to ask for (decision 7
    of the quality assurance stage)."""
    step, _, _ = _checkpoint(tmp_path, product, checkpoint=4)
    with pytest.raises(ValueError, match="on the code host"):
        step.decide()


def test_the_published_release_opens(product, tmp_path):
    step, _, host = _checkpoint(tmp_path, product, checkpoint=5)
    opened = []
    step.opener = lambda page: opened.append(page) or page
    assert step.release_page("1.0.0", deadline=0) is None  # not published yet
    page = f"https://github.com/{HOST_REPO}/releases/tag/v1.0.0"
    step.host.data[HOST_REPO]["releases"] = {"v1.0.0": page}
    assert step.release_page("1.0.0", deadline=0) == page
    assert opened == [page]


def test_an_approval_is_current_while_the_files_are_unchanged(product):
    approve_checkpoint(product, 2)
    config = read_product_config(product)
    assert current_approval(config, 2, "requirements")[0] is not None
    path = product / "docs/requirements/login.md"
    path.write_text(path.read_text() + "\n")
    approval, reason = current_approval(config, 2, "requirements")
    assert approval is None
    assert "changed" in reason
