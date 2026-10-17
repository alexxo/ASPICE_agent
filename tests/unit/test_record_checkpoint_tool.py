"""agent/record_checkpoint_tool.py — writes a checkpoint decision as approval.v1."""

from datetime import datetime, timezone

import pytest

from agent.record_checkpoint_tool import current_approval, record_checkpoint, subject_files
from tools.read_product_config_tool import read_product_config
from tools.read_yaml_blocks_tool import read_yaml_file
from tools.validate_contract_tool import validate

NOW = datetime(2026, 10, 4, 14, 20, tzinfo=timezone.utc)


def test_requirements_subject_is_the_requirement_files_and_the_glossary(product):
    files = subject_files(read_product_config(product), "requirements")
    assert [f.relative_to(product).as_posix() for f in files] == [
        "docs/glossary.md",
        "docs/requirements/login.md",
        "docs/requirements/review.html",
    ]


def test_diagrams_subject_is_the_specs_invariants_pictures_and_review_page(product):
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
        "docs/glossary.md",
        "docs/requirements/login.md",
        "docs/requirements/review.html",
    ]


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
