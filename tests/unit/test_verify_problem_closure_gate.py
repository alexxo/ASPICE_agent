"""gates/sup/verify_problem_closure_gate.py — closed with its fix and its finder's word."""

import pytest
from product_builder import (
    BEFORE,
    PERSON,
    REPORTER,
    build_releasable_product,
    comment,
    commit_all,
    git_head,
    issue,
    problem,
    propose_release,
    write_host,
    write_problem_test,
)

from gates.sup.verify_problem_closure_gate import GATE, check
from tools.read_product_config_tool import read_product_config

CONFIRM = "/confirm-fixed"


@pytest.fixture
def product(tmp_path, monkeypatch):
    root, host = build_releasable_product(tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return root


def issues(root, tmp_path, monkeypatch, *found):
    framework = git_head(root / ".framework")
    path = write_host(tmp_path / "issues.json", tags={"v6.0.0": framework}, issues=found)
    monkeypatch.setenv("QF_HOST_FILE", str(path))


def rules(root):
    return sorted((f.rule, f.file) for f in check(read_product_config(root)))


def closed(number, **changes):
    said = changes.pop("comments", (comment(REPORTER, CONFIRM),))
    return issue(number, "problem", problem(number, status="closed", **changes), state="closed",
                 closed="2099-01-02T09:00:00Z", comments=said)  # fmt: skip


def test_gate_name_follows_the_convention():
    assert GATE == "verify_problem_closure_gate"


def test_a_marker_naming_no_problem_is_reported_at_its_line(product, tmp_path, monkeypatch):
    path = write_problem_test(product, 99)
    issues(product, tmp_path, monkeypatch)
    findings = check(read_product_config(product))
    assert [(f.rule, f.file, f.line) for f in findings] == [("UNKNOWN_PROBLEM", path, 1)]


def test_a_problem_fixed_and_confirmed_passes_at_release(product, tmp_path, monkeypatch):
    write_problem_test(product, 12)
    commit_all(product, "test: reproduce #12")  # on main: the fix has merged
    propose_release(product)
    issues(product, tmp_path, monkeypatch, closed(12))
    assert rules(product) == []


def test_a_fixed_problem_without_its_test_is_reported(product, tmp_path, monkeypatch):
    propose_release(product)
    issues(product, tmp_path, monkeypatch, issue(12, "problem", problem(12, status="fixed")))
    assert rules(product) == [("MISSING_PROBLEM_TEST", "#12")]


def test_a_closed_problem_needs_its_fix_on_main_or_a_change_request(product, tmp_path, monkeypatch):
    propose_release(product)
    write_problem_test(product, 13)
    commit_all(product, "test: reproduce #13 on the release branch only")
    issues(product, tmp_path, monkeypatch, closed(13), closed(14, change_request=20))
    assert rules(product) == [("CLOSED_WITHOUT_FIX", "#13")]


def test_only_the_reporter_confirms_and_only_after_the_fix(product, tmp_path, monkeypatch):
    write_problem_test(product, 12)
    write_problem_test(product, 13)
    commit_all(product, "test: reproduce #12 and #13")
    propose_release(product)
    issues(
        product,
        tmp_path,
        monkeypatch,
        closed(12, comments=[comment(PERSON, CONFIRM)]),
        closed(13, comments=[comment(REPORTER, CONFIRM, BEFORE)]),
    )
    assert rules(product) == [("MISSING_CONFIRMATION", "#12"), ("MISSING_CONFIRMATION", "#13")]


def test_without_a_release_only_the_markers_are_checked(product, tmp_path, monkeypatch):
    issues(product, tmp_path, monkeypatch, issue(12, "problem", problem(12, status="fixed")))
    assert rules(product) == []
