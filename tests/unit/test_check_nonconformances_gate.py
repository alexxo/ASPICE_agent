"""gates/sup/check_nonconformances_gate.py, check_escalations_gate.py, check_retro_actions_gate.py
— the faults left open and the lessons learned, at release."""

from datetime import date, datetime, timezone

import pytest
from product_builder import (
    AUTHOR,
    PERSON,
    build_releasable_product,
    comment,
    git_head,
    issue,
    propose_release,
    pull_request,
    write_host,
)

from gates.sup import check_escalations_gate, check_nonconformances_gate, check_retro_actions_gate
from tools.read_product_config_tool import read_product_config

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
OLD = "2026-08-01T09:00:00Z"  # 72 days before NOW, beyond escalate_after_days (30)
NEW = "2026-10-01T09:00:00Z"


@pytest.fixture
def product(tmp_path, monkeypatch):
    root, host = build_releasable_product(tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    propose_release(root)
    return root


def host(root, tmp_path, monkeypatch, *found, pulls=()):
    framework = git_head(root / ".framework")
    path = write_host(
        tmp_path / "issues.json", tags={"v6.0.0": framework}, issues=found, pulls=pulls
    )
    monkeypatch.setenv("QF_HOST_FILE", str(path))


def rules(gate, root, **when):
    return sorted((f.rule, f.file) for f in gate.check(read_product_config(root), **when))


def test_gate_names_follow_the_convention():
    assert check_nonconformances_gate.GATE == "check_nonconformances_gate"
    assert check_escalations_gate.GATE == "check_escalations_gate"
    assert check_retro_actions_gate.GATE == "check_retro_actions_gate"


def test_a_closed_fault_needs_the_merged_pull_request_that_fixed_it(product, tmp_path, monkeypatch):
    nc = "non-conformance"
    host(
        product,
        tmp_path,
        monkeypatch,
        issue(1, nc, {"found_in": 3, "fixed_by": 4}, state="closed"),
        issue(2, nc, {"found_in": 3}, state="closed"),
        issue(3, nc, {"found_in": 3, "fixed_by": 5}, state="closed"),
        issue(4, nc, None, state="closed"),
        issue(5, nc, {"found_in": 3}),  # still open
        pulls=[pull_request(4, "h4", merged=True), pull_request(5, "h5")],
    )
    assert rules(check_nonconformances_gate, product) == [
        ("NONCONFORMANCE_WITHOUT_FIX", "#2"),
        ("NONCONFORMANCE_WITHOUT_FIX", "#3"),
        ("NONCONFORMANCE_WITHOUT_FIX", "#4"),
    ]


def test_an_accepted_delivery_that_was_right_closes_without_a_fix(product, tmp_path, monkeypatch):
    """Its acceptance closes it: an urgent approver's /accept-delivery, never its author's."""
    nc = "non-conformance"
    accept = "/accept-delivery"
    host(
        product,
        tmp_path,
        monkeypatch,
        issue(1, nc, {"found_in": 6}, state="closed", comments=[comment(PERSON, accept)]),
        issue(2, nc, {"commit": "38c2eb2"}, state="closed", comments=[comment(PERSON, accept)]),
        issue(3, nc, {"found_in": 6}, state="closed", comments=[comment(AUTHOR, accept)]),
        issue(4, nc, {"found_in": 8}, state="closed", comments=[comment(PERSON, accept)]),
        issue(5, nc, {"found_in": 6}, state="closed", comments=[comment(PERSON, "looks fine")]),
        pulls=[pull_request(6, "h6", merged=True), pull_request(8, "h8", author=PERSON)],
    )
    assert rules(check_nonconformances_gate, product) == [
        ("NONCONFORMANCE_WITHOUT_FIX", "#3"),
        ("NONCONFORMANCE_WITHOUT_FIX", "#4"),
        ("NONCONFORMANCE_WITHOUT_FIX", "#5"),
    ]


def test_an_old_open_fault_must_be_escalated_and_assigned(product, tmp_path, monkeypatch):
    nc = "non-conformance"
    host(
        product,
        tmp_path,
        monkeypatch,
        issue(1, nc, {"found_in": 3}, created=OLD),
        issue(2, nc, {"found_in": 3}, created=OLD, labels=["escalated"]),
        issue(3, nc, {"found_in": 3}, created=OLD, labels=["escalated"], assignees=[PERSON]),
        issue(4, nc, {"found_in": 3}, created=NEW),
        issue(5, nc, {"found_in": 3, "fixed_by": 4}, created=OLD, state="closed"),
    )
    assert rules(check_escalations_gate, product, now=NOW) == [
        ("UNESCALATED_NONCONFORMANCE", "#1"),
        ("UNESCALATED_NONCONFORMANCE", "#2"),
    ]


def test_an_open_lesson_past_its_due_date_is_reported(product, tmp_path, monkeypatch):
    ra = "retro-action"
    host(
        product,
        tmp_path,
        monkeypatch,
        issue(1, ra, {"owner": PERSON, "due": "2026-10-01"}),
        issue(2, ra, {"owner": PERSON, "due": "2026-11-01"}),
        issue(3, ra, None),
        issue(4, ra, {"owner": PERSON, "due": "2026-10-01"}, state="closed"),
    )
    assert rules(check_retro_actions_gate, product, today=date(2026, 10, 12)) == [
        ("OVERDUE_RETRO_ACTION", "#1"),
        ("OVERDUE_RETRO_ACTION", "#3"),
    ]


def test_without_a_release_nothing_is_read(tmp_path, monkeypatch):
    root, _host = build_releasable_product(tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(tmp_path / "no-host.json"))  # would crash if read
    config = read_product_config(root)
    for gate in (check_nonconformances_gate, check_escalations_gate, check_retro_actions_gate):
        assert gate.check(config) == []
