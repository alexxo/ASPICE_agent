"""gates/val/verify_release_evidence_gate.py — what is released was validated, and accepted."""

from datetime import datetime, timezone

import pytest
from product_builder import (
    ALL_SCENARIOS,
    DEMO,
    SCENARIO_TESTS,
    build_releasable_product,
    commit_all,
    git_head,
    passed,
    propose_release,
    record_validation,
    tag_release,
)

from agent.record_checkpoint_tool import record_checkpoint
from gates.val.verify_release_evidence_gate import GATE, check
from tools.read_product_config_tool import read_product_config

RECORD = "validation/records/1.0.0.yaml"
DECIDED = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def product(tmp_path, monkeypatch):
    root, host = build_releasable_product(tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return root


@pytest.fixture
def proposed(product):
    propose_release(product)
    return product


def decide(root, decision="approved", comment=None):
    record_checkpoint(root, 5, decision, "Carla Village", "customer", comment, now=DECIDED)
    commit_all(root, "docs(approvals): the customer's decision #2")


def rules(root):
    return sorted((f.rule, f.file) for f in check(read_product_config(root)))


def test_gate_name_follows_the_convention():
    assert GATE == "verify_release_evidence_gate"


def test_without_a_release_there_is_nothing_to_check(product):
    assert rules(product) == []


def test_a_proposed_release_needs_its_validation_record(proposed):
    assert ("MISSING_VALIDATION_RECORD", RECORD) in rules(proposed)


def test_a_record_that_breaks_its_contract_counts_as_missing(proposed):
    (proposed / "validation/records").mkdir(parents=True)
    (proposed / RECORD).write_text("contract: validation.v1\nversion: 1.0.0\n")
    assert ("MISSING_VALIDATION_RECORD", RECORD) in rules(proposed)


def test_a_validated_release_waits_for_the_customer(proposed):
    record_validation(proposed, passed(*ALL_SCENARIOS))
    assert rules(proposed) == [("MISSING_CUSTOMER_DECISION", "docs/approvals")]


def test_a_release_the_customer_accepted_passes(proposed):
    record_validation(proposed, passed(*ALL_SCENARIOS))
    decide(proposed)
    assert rules(proposed) == []


def test_an_acceptance_in_another_role_does_not_count(proposed):
    record_validation(proposed, passed(*ALL_SCENARIOS))
    decide(proposed)
    (approval,) = (proposed / "docs/approvals").glob("*-checkpoint-5-release.yaml")
    approval.write_text(approval.read_text().replace("role: customer", "role: architect"))
    assert rules(proposed) == [("MISSING_CUSTOMER_DECISION", "docs/approvals")]


def test_a_rejection_is_reported_with_its_reason(proposed):
    record_validation(proposed, passed(*ALL_SCENARIOS))
    decide(proposed, "changes-requested", comment="The lock message scares people.")
    findings = check(read_product_config(proposed))
    assert [f.rule for f in findings] == ["RELEASE_REJECTED"]
    assert "The lock message scares people." in findings[0].message


def test_a_record_changed_after_the_acceptance_withdraws_it(proposed):
    record_validation(proposed, passed(*ALL_SCENARIOS))
    decide(proposed)
    record_validation(proposed, passed(*ALL_SCENARIOS), commit=git_head(proposed))
    assert ("MISSING_CUSTOMER_DECISION", "docs/approvals") in rules(proposed)


def test_failed_unknown_and_missing_results_are_reported(proposed):
    results = [
        *passed(SCENARIO_TESTS["W-01"], result="fail"),
        *passed(DEMO),
        *passed("validation/scenarios/test_gone.py"),
    ]
    record_validation(proposed, results)
    decide(proposed)
    assert rules(proposed) == [
        ("FAILED_SCENARIO", SCENARIO_TESTS["W-01"]),
        ("MISSING_RESULT", SCENARIO_TESTS["W-03"]),
        ("UNKNOWN_SCENARIO", RECORD),
    ]


def test_a_scenario_run_by_hand_may_be_left_out(proposed):
    record_validation(proposed, passed(SCENARIO_TESTS["W-01"], SCENARIO_TESTS["W-03"]))
    decide(proposed)
    assert rules(proposed) == []


def test_a_change_after_the_deployment_is_not_what_was_validated(proposed):
    deployed = git_head(proposed)
    (proposed / "src/late_fix.py").write_text("FIX = 1\n")
    commit_all(proposed, "fix(web): a late fix #2")
    record_validation(proposed, passed(*ALL_SCENARIOS), commit=deployed)
    decide(proposed)
    assert rules(proposed) == [("WRONG_DEPLOYED_COMMIT", RECORD)]


def test_a_deployment_before_the_release_record_is_not_the_release(product):
    deployed = git_head(product)
    propose_release(product)
    record_validation(product, passed(*ALL_SCENARIOS), commit=deployed)
    decide(product)
    assert rules(product) == [("WRONG_DEPLOYED_COMMIT", RECORD)]


def test_a_deployment_outside_the_history_is_not_the_release(proposed):
    record_validation(proposed, passed(*ALL_SCENARIOS), commit="0" * 40)
    decide(proposed)
    assert rules(proposed) == [("WRONG_DEPLOYED_COMMIT", RECORD)]


def test_a_copy_of_the_release_outside_its_history_is_not_the_release(proposed):
    import subprocess

    def git(*args):
        run = ["git", "-C", str(proposed), *args]
        return subprocess.run(run, capture_output=True, text=True, check=True).stdout.strip()

    copy = git(
        "-c", "user.name=t", "-c", "user.email=t@e.org",
        "commit-tree", "HEAD^{tree}", "-p", "HEAD~1", "-m", "the same tree, rebased",
    )  # fmt: skip
    record_validation(proposed, passed(*ALL_SCENARIOS), commit=copy)
    decide(proposed)
    assert rules(proposed) == [("WRONG_DEPLOYED_COMMIT", RECORD)]


def test_every_release_tag_holds_its_validation_record(proposed):
    tag_release(proposed, "1.0.0")
    assert rules(proposed) == [("MISSING_VALIDATION_RECORD", RECORD)]


def test_a_tagged_release_with_its_record_passes(proposed):
    record_validation(proposed, passed(*ALL_SCENARIOS))
    decide(proposed)
    tag_release(proposed, "1.0.0")
    assert rules(proposed) == []
