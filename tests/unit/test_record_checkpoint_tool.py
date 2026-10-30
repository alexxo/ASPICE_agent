"""agent/record_checkpoint_tool.py — writes a checkpoint decision as approval.v1."""

from datetime import datetime, timezone

import pytest

from agent.record_checkpoint_tool import current_approval, record_checkpoint, subject_files
from tools.read_product_config_tool import read_product_config
from tools.read_yaml_blocks_tool import read_yaml_file
from tools.validate_contract_tool import validate

NOW = datetime(2026, 10, 4, 14, 20, tzinfo=timezone.utc)


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


def test_record_writes_a_valid_dated_approval(product):
    path = record_checkpoint(product, 2, "approved", "Alex", "architect", now=NOW)
    assert path.name == "2026-10-04T142000Z-checkpoint-2-requirements.yaml"
    data = read_yaml_file(path)
    assert validate(data, "approval") == []
    assert [s["path"] for s in data["subject"]] == [
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


def test_an_approval_on_a_stale_review_page_is_refused(product):
    """The person approves the requirements they saw (§ 5 stages 1 and 2, rule 24)."""
    login = product / "docs/requirements/login.md"
    login.write_text(login.read_text().replace("Five failed", "Three failed"))
    with pytest.raises(ValueError, match="not what the files render now"):
        record_checkpoint(product, 2, "approved", "Alex", "architect", now=NOW)
    (product / "docs/requirements/review.html").unlink()
    with pytest.raises(ValueError, match="missing"):
        record_checkpoint(product, 2, "approved", "Alex", "architect", now=NOW)
    path = record_checkpoint(product, 2, "changes-requested", "Alex", "architect", "No.", NOW)
    assert path.is_file()  # asking for changes needs no page


def test_changes_requested_needs_a_comment(product):
    with pytest.raises(ValueError):
        record_checkpoint(product, 2, "changes-requested", "Alex", "architect", now=NOW)


def test_the_wrong_role_is_refused(product):
    with pytest.raises(ValueError):
        record_checkpoint(product, 2, "approved", "Pat", "customer", now=NOW)


def test_an_approval_is_current_while_the_files_are_unchanged(product):
    record_checkpoint(product, 2, "approved", "Alex", "architect", now=NOW)
    config = read_product_config(product)
    assert current_approval(config, 2, "requirements")[0] is not None
    path = product / "docs/requirements/login.md"
    path.write_text(path.read_text() + "\n")
    approval, reason = current_approval(config, 2, "requirements")
    assert approval is None
    assert "changed" in reason


def test_the_latest_decision_counts(product):
    record_checkpoint(product, 2, "approved", "Alex", "architect", now=NOW)
    later = NOW.replace(hour=15)
    record_checkpoint(
        product, 2, "changes-requested", "Alex", "architect", "Reword REQ-0011.", now=later
    )
    approval, reason = current_approval(read_product_config(product), 2, "requirements")
    assert approval is None
    assert "Reword REQ-0011." in reason


def test_seal_4_is_never_a_file_the_agent_writes(product):
    """A person's approval of a pull request lives on the host (decision 7 of
    the quality assurance stage): a file the agent can write proves nothing."""
    with pytest.raises(ValueError, match="on the code host"):
        record_checkpoint(product, 4, "approved", "Lead", "reviewer", now=NOW)


# --- the person decides on the code host; the tool copies the review (FB-69) ---


def _host(tmp_path, monkeypatch, product, *reviews):
    from product_builder import add_origin, git_head, pull_request, write_host

    add_origin(product)
    pull = pull_request(7, git_head(product), files=["docs/requirements/login.md"], reviews=reviews)
    monkeypatch.setenv("QF_HOST_FILE", str(write_host(tmp_path / "host.json", pulls=[pull])))
    return git_head(product)


def test_the_persons_approval_on_the_host_is_copied(product, tmp_path, monkeypatch):
    from product_builder import PERSON, git_head, review

    from agent.record_checkpoint_tool import record_from_host

    head = git_head(product)
    _host(tmp_path, monkeypatch, product, review(PERSON, head, id=41))
    path = record_from_host(product, 2, 7, now=NOW)
    data = read_yaml_file(path)
    assert (data["decision"], data["approver"]) == (
        "approved",
        {"name": PERSON, "role": "architect"},
    )
    assert data["review"] == {"pull_request": 7, "id": 41, "commit": head}
    assert validate(data, "approval") == []
    assert record_from_host(product, 2, 7) == path  # copied once
    approval, _ = current_approval(read_product_config(product), 2, "requirements")
    assert approval == path


def test_no_person_has_decided_yet(product, tmp_path, monkeypatch):
    """The agent's, a bot's and the author's reviews decide nothing."""
    from product_builder import AGENT, AUTHOR, git_head, review

    from agent.record_checkpoint_tool import Waiting, main, record_from_host

    head = git_head(product)
    _host(tmp_path, monkeypatch, product, review(AGENT, head, id=1), review(AUTHOR, head, id=2))
    with pytest.raises(Waiting, match="pull/7/files"):
        record_from_host(product, 2, 7)
    assert main(["--root", str(product), "--checkpoint", "2", "--pull-request", "7"]) == 3


def test_a_review_of_files_changed_since_is_not_copied(product, tmp_path, monkeypatch):
    from product_builder import PERSON, commit_all, git_head, review

    from agent.record_checkpoint_tool import Waiting, record_from_host

    reviewed = git_head(product)
    glossary = product / "docs" / "glossary.md"
    glossary.write_text(glossary.read_text() + "\n")
    commit_all(product, "docs: a blank line")
    _host(tmp_path, monkeypatch, product, review(PERSON, reviewed, id=41))
    with pytest.raises(Waiting, match="docs/glossary.md changed since"):
        record_from_host(product, 2, 7)


def test_a_request_for_changes_is_copied_with_its_reason(product, tmp_path, monkeypatch):
    from product_builder import PERSON, git_head, review

    from agent.record_checkpoint_tool import record_from_host

    _host(
        tmp_path, monkeypatch, product, review(PERSON, git_head(product), "CHANGES_REQUESTED", id=9)
    )
    data = read_yaml_file(record_from_host(product, 2, 7, now=NOW))
    assert (data["decision"], data["comment"]) == ("changes-requested", "Looks right.")
