"""tools/read_approvals_tool.py — whether a checkpoint's latest decision still counts."""

from datetime import datetime, timezone

from agent.record_checkpoint_tool import record_checkpoint
from tools.read_approvals_tool import approval_state, subject_files
from tools.read_product_config_tool import read_product_config

NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)


def _state(root):
    return approval_state(read_product_config(root), 1, "diagrams")


def test_no_decision_is_missing(product):
    assert _state(product).status == "missing"


def test_a_current_approval_is_approved_with_its_date(product):
    record_checkpoint(product, 1, "approved", "Alex", "architect", now=NOW)
    state = _state(product)
    assert (state.status, state.date) == ("approved", NOW)


def test_changes_requested_counts_as_not_approved(product):
    record_checkpoint(
        product, 1, "changes-requested", "Alex", "architect", "Add an error path.", now=NOW
    )
    assert _state(product).status == "changes_requested"


def test_a_changed_file_makes_the_approval_outdated(product):
    record_checkpoint(product, 1, "approved", "Alex", "architect", now=NOW)
    (product / "docs/diagrams/login.wishes.yaml").write_text(
        "diagram: login\nlinks: {user: [W-01]}\n"
    )
    state = _state(product)
    assert state.status == "outdated" and "login.wishes.yaml" in state.reason


def test_an_added_file_makes_the_approval_outdated(product):
    record_checkpoint(product, 1, "approved", "Alex", "architect", now=NOW)
    (product / "docs/diagrams/extra.invariants.yaml").write_text("diagram: extra\n")
    assert _state(product).status == "outdated"


def test_an_unreadable_decision_is_invalid(product):
    folder = product / "docs/approvals"
    (folder / "2026-10-04T090000Z-checkpoint-1-diagrams.yaml").write_text("checkpoint: [\n")
    assert _state(product).status == "invalid"


def test_the_release_decision_covers_both_records_and_is_due_only_for_a_release(
    tmp_path, monkeypatch
):
    from product_builder import (
        ALL_SCENARIOS,
        build_releasable_product,
        passed,
        propose_release,
        record_validation,
        tag_release,
    )

    from tools.read_approvals_tool import checkpoint_due, subject_files

    root, host = build_releasable_product(tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    config = read_product_config(root)
    assert (checkpoint_due(config, "release"), subject_files(config, "release")) == (False, [])
    assert checkpoint_due(config, "requirements")
    propose_release(root)
    record_validation(root, passed(*ALL_SCENARIOS))
    assert checkpoint_due(config, "release")
    assert [config.relative(f) for f in subject_files(config, "release")] == [
        "releases/1.0.0.yaml",
        "validation/records/1.0.0.yaml",
    ]
    tag_release(root, "1.0.0")
    assert not checkpoint_due(config, "release")


def test_the_approval_covers_what_the_person_saw_and_what_it_is_derived_from(product):
    """The pictures, the review page, and the diagrams under the requirements
    (§ 5 stages 1–2, rule 25)."""
    config = read_product_config(product)
    diagrams = {config.relative(f) for f in subject_files(config, "diagrams")}
    assert {
        "docs/diagrams/auth-flow.architecture.html",
        "docs/diagrams/login.sequence.html",
    } <= diagrams
    (product / "docs/diagrams/review.html").write_text("left over\n")
    assert "docs/diagrams/review.html" not in {
        config.relative(f) for f in subject_files(config, "diagrams")
    }
    requirements = {config.relative(f) for f in subject_files(config, "requirements")}
    assert {"docs/requirements/review.html", "docs/diagrams/login.sequence.json"} <= requirements
    assert "docs/diagrams/login.sequence.html" not in requirements
