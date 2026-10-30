"""tools/read_approvals_tool.py — whether a checkpoint's latest decision still counts.

The decision is the merge of the checkpoint's pull request, read from git history.
"""

from product_builder import approve_checkpoint, commit_all

from tools.read_approvals_tool import approval_state, checkpoint_merges, subject_files
from tools.read_product_config_tool import read_product_config


def _state(root):
    return approval_state(read_product_config(root), 1, "diagrams")


def test_no_merged_checkpoint_pull_request_is_missing(product):
    state = _state(product)
    assert state.status == "missing" and "checkpoint/1" in state.reason


def test_the_merge_of_the_checkpoints_pull_request_approves(product):
    merge = approve_checkpoint(product, 1, number=7)
    state = _state(product)
    assert (state.status, state.merge.number, state.merge.commit) == ("approved", 7, merge)
    assert state.merge.head != merge  # the approved head is the merge's second parent


def test_a_merge_of_another_branch_approves_nothing(product):
    approve_checkpoint(product, 2)
    assert _state(product).status == "missing"


def test_a_changed_file_makes_the_approval_outdated(product):
    approve_checkpoint(product, 1)
    (product / "docs/diagrams/login.wishes.yaml").write_text(
        "diagram: login\nlinks: {user: [W-01]}\n"
    )
    state = _state(product)
    assert state.status == "outdated" and "login.wishes.yaml" in state.reason
    commit_all(product, "docs: a committed change counts the same")
    assert _state(product).status == "outdated"


def test_an_added_file_makes_the_approval_outdated(product):
    approve_checkpoint(product, 1)
    (product / "docs/diagrams/extra.invariants.yaml").write_text("diagram: extra\n")
    assert _state(product).status == "outdated"


def test_the_latest_merge_counts(product):
    approve_checkpoint(product, 1, number=3)
    (product / "docs/diagrams/extra.invariants.yaml").write_text("diagram: extra\n")
    approve_checkpoint(product, 1, number=9)
    state = _state(product)
    assert (state.status, state.merge.number) == ("approved", 9)
    assert [m.number for m in checkpoint_merges(product, 1)] == [3, 9]


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
        "docs/diagrams/review.html",
    } <= diagrams
    requirements = {config.relative(f) for f in subject_files(config, "requirements")}
    assert {"docs/requirements/review.html", "docs/diagrams/login.sequence.json"} <= requirements
    assert "docs/diagrams/login.sequence.html" not in requirements
