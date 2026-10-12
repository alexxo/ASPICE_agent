"""gates/sup/check_change_record_gate.py, verify_change_approval_gate.py,
verify_change_trace_gate.py, verify_change_closure_gate.py — the change desk."""

import json
import subprocess

import pytest
from product_builder import (
    AFTER,
    BEFORE,
    PERSON,
    REPORTER,
    build_releasable_product,
    change,
    comment,
    commit_all,
    git_head,
    issue,
    problem,
    propose_release,
    write_host,
)

from gates.sup import (
    check_change_record_gate,
    verify_change_approval_gate,
    verify_change_closure_gate,
    verify_change_trace_gate,
)
from tools.read_product_config_tool import read_product_config
from tools.write_verification_report_tool import write_report

CR = "change-request"
SIGNED = comment(PERSON, "/approve-change", BEFORE)


@pytest.fixture
def product(tmp_path, monkeypatch):
    root, host = build_releasable_product(tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return root


def host(root, tmp_path, monkeypatch, *found):
    framework = git_head(root / ".framework")
    path = write_host(tmp_path / "issues.json", tags={"v6.0.0": framework}, issues=found)
    monkeypatch.setenv("QF_HOST_FILE", str(path))


def build(root, number=20, branch="feature/REQ-0047-lock-later"):
    """A pull request whose commit builds change request number."""
    if branch:
        subprocess.run(["git", "-C", str(root), "checkout", "-q", "-b", branch], check=True)
    (root / "src/later.py").write_text("LIMIT = 10\n")
    commit_all(root, f"feat(auth): lock later #{number}")


def rules(gate, root):
    return sorted((f.rule, f.file) for f in gate.check(read_product_config(root)))


def test_gate_names_follow_the_convention():
    for gate in (
        check_change_record_gate,
        verify_change_approval_gate,
        verify_change_trace_gate,
        verify_change_closure_gate,
    ):
        assert gate.__name__.split(".")[-1] == gate.GATE


def test_without_a_change_or_a_release_nothing_is_read(product, tmp_path, monkeypatch):
    monkeypatch.setenv("QF_HOST_FILE", str(tmp_path / "no-host.json"))  # would crash if read
    for gate in (check_change_record_gate, verify_change_trace_gate, verify_change_closure_gate):
        assert gate.check(read_product_config(product)) == []


# ── the record (BP1, BP2) ──────────────────────────────────────────────────


def test_a_change_being_built_must_be_recorded_and_analysed(product, tmp_path, monkeypatch):
    build(product, 20)
    commit_all(product, "feat(auth): and the others #21 #22")
    host(
        product,
        tmp_path,
        monkeypatch,
        issue(20, CR, None),
        issue(21, CR, change(21, status="requested", affected=None, size=None)),
        issue(22, CR, change(22, depends_on=[99])),
        issue(23, CR, None),  # nobody builds it yet
    )
    assert rules(check_change_record_gate, product) == [
        ("INCOMPLETE_CHANGE_RECORD", "#20"),
        ("MISSING_CHANGE_ANALYSIS", "#21"),
        ("UNKNOWN_DEPENDENCY", "#22"),
    ]


def test_at_release_every_change_past_requested_is_analysed(product, tmp_path, monkeypatch):
    propose_release(product)
    host(
        product,
        tmp_path,
        monkeypatch,
        issue(20, CR, change(20, size=None)),
        issue(21, CR, change(21, status="requested", affected=None, size=None)),
    )
    assert rules(check_change_record_gate, product) == [("MISSING_CHANGE_ANALYSIS", "#20")]


# ── the approval (BP3) ─────────────────────────────────────────────────────


def test_a_change_is_built_only_after_an_approver_signed_it(product, tmp_path, monkeypatch):
    build(product, 20)
    host(product, tmp_path, monkeypatch, issue(20, CR, change(20)))
    assert rules(verify_change_approval_gate, product) == [("UNAPPROVED_CHANGE", "#20")]
    late = comment(PERSON, "/approve-change", AFTER)
    host(product, tmp_path, monkeypatch, issue(20, CR, change(20), comments=[late]))
    assert rules(verify_change_approval_gate, product) == [("UNAPPROVED_CHANGE", "#20")]
    other = comment(REPORTER, "/approve-change", BEFORE)
    host(product, tmp_path, monkeypatch, issue(20, CR, change(20), comments=[other]))
    assert rules(verify_change_approval_gate, product) == [("UNAPPROVED_CHANGE", "#20")]
    host(product, tmp_path, monkeypatch, issue(20, CR, change(20), comments=[SIGNED]))
    assert rules(verify_change_approval_gate, product) == []


def test_a_change_nobody_builds_needs_no_signature_yet(product, tmp_path, monkeypatch):
    host(product, tmp_path, monkeypatch, issue(20, CR, change(20)))
    assert rules(verify_change_approval_gate, product) == []


# ── the trace (BP4) ────────────────────────────────────────────────────────


def test_every_affected_item_exists(product, tmp_path, monkeypatch):
    build(product, 20)
    unknown = {"wishes": ["W-09"], "elements": ["login#nope"], "requirements": ["REQ-9999"]}
    host(product, tmp_path, monkeypatch, issue(20, CR, change(20, affected=unknown)))
    assert rules(verify_change_trace_gate, product) == [("UNKNOWN_AFFECTED_ITEM", "#20")] * 3
    host(product, tmp_path, monkeypatch, issue(20, CR, change(20)))
    assert rules(verify_change_trace_gate, product) == []


def test_a_change_and_its_problem_name_each_other(product, tmp_path, monkeypatch):
    propose_release(product)
    host(
        product,
        tmp_path,
        monkeypatch,
        issue(20, CR, change(20, problem=12)),
        issue(12, "problem", problem(12)),  # does not name #20 back
        issue(21, CR, change(21)),
        issue(13, "problem", problem(13, change_request=21)),  # #21 does not name it back
        issue(22, CR, change(22, problem=14)),
        issue(14, "problem", problem(14, change_request=22)),  # linked both ways
    )
    assert rules(verify_change_trace_gate, product) == [
        ("UNLINKED_PROBLEM", "#13"),
        ("UNLINKED_PROBLEM", "#20"),
    ]


# ── the closure (BP5, BP6) ─────────────────────────────────────────────────


def closed(number, *said):
    return issue(number, CR, change(number, status="closed"), state="closed", comments=said)


def test_a_closed_change_is_built_on_main_and_confirmed(product, tmp_path, monkeypatch):
    build(product, 20, branch=None)  # merged: on main
    propose_release(product)
    confirmed = comment(REPORTER, "/confirm-change")
    host(
        product,
        tmp_path,
        monkeypatch,
        closed(20, confirmed),
        closed(21, confirmed),  # nothing on main names it
        closed(22),
    )
    assert rules(verify_change_closure_gate, product) == [
        ("CLOSED_WITHOUT_IMPLEMENTATION", "#21"),
        ("CLOSED_WITHOUT_IMPLEMENTATION", "#22"),
        ("MISSING_CHANGE_CONFIRMATION", "#22"),
    ]


def test_only_the_initiator_confirms_and_only_after_the_last_commit(product, tmp_path, monkeypatch):
    build(product, 20, branch=None)
    propose_release(product)
    host(product, tmp_path, monkeypatch, closed(20, comment(PERSON, "/confirm-change")))
    assert rules(verify_change_closure_gate, product) == [("MISSING_CHANGE_CONFIRMATION", "#20")]
    host(product, tmp_path, monkeypatch, closed(20, comment(REPORTER, "/confirm-change", BEFORE)))
    assert rules(verify_change_closure_gate, product) == [("MISSING_CHANGE_CONFIRMATION", "#20")]


def test_the_release_report_lists_the_changes(product, tmp_path, monkeypatch):
    build(product, 20, branch=None)
    propose_release(product)
    host(product, tmp_path, monkeypatch, issue(20, CR, change(20)), issue(21, CR, change(21)))
    written = write_report(read_product_config(product))
    report = json.loads(written.read_text())
    assert report["changes"] == {"implemented": [20], "open": [20, 21]}
    assert rules(verify_change_closure_gate, product) == []
    del report["changes"]
    written.write_text(json.dumps(report))
    assert [r for r, _ in rules(verify_change_closure_gate, product)] == ["MISSING_CHANGE_SECTION"]
