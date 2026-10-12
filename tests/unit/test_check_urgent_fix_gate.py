"""gates/sup/check_urgent_fix_gate.py — an urgent fix is authorized before it merges."""

import pytest
from product_builder import (
    AUTHOR,
    BEFORE,
    PERSON,
    build_releasable_product,
    comment,
    commit_all,
    git_head,
    issue,
    problem,
    write_host,
    write_problem_test,
)

from gates.sup.check_urgent_fix_gate import GATE, check
from tools.read_product_config_tool import read_product_config

COMMAND = "/authorize-urgent-fix"


@pytest.fixture
def product(tmp_path, monkeypatch):
    root, host = build_releasable_product(tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return root


def critical(root, tmp_path, monkeypatch, *said):
    framework = git_head(root / ".framework")
    found = [issue(12, "problem", problem(12, severity="critical"), comments=said)]
    path = write_host(tmp_path / "issues.json", tags={"v6.0.0": framework}, issues=found)
    monkeypatch.setenv("QF_HOST_FILE", str(path))


def rules(root):
    return [(f.rule, f.file) for f in check(read_product_config(root))]


def fix(root, branch=True):
    """The crack bench, on a bugfix branch (the fixing pull request) or on main."""
    import subprocess

    if branch:
        subprocess.run(["git", "-C", str(root), "checkout", "-q", "-b", "bugfix/REQ-0047-lock"])
    path = write_problem_test(root, 12)
    commit_all(root, "test: reproduce #12")
    return path


def test_gate_name_follows_the_convention():
    assert GATE == "check_urgent_fix_gate"


def test_an_unauthorized_critical_fix_is_reported_at_its_test(product, tmp_path, monkeypatch):
    path = fix(product)
    critical(product, tmp_path, monkeypatch)
    assert rules(product) == [("UNAUTHORIZED_URGENT_FIX", path)]


def test_only_an_urgent_approver_can_authorize(product, tmp_path, monkeypatch):
    path = fix(product)
    critical(product, tmp_path, monkeypatch, comment(AUTHOR, COMMAND))
    assert rules(product) == [("UNAUTHORIZED_URGENT_FIX", path)]
    critical(product, tmp_path, monkeypatch, comment(PERSON, f"{COMMAND}\nGo ahead."))
    assert rules(product) == []


def test_after_the_merge_the_authorization_must_have_come_first(product, tmp_path, monkeypatch):
    path = fix(product, branch=False)
    critical(product, tmp_path, monkeypatch, comment(PERSON, COMMAND))  # given after the merge
    assert rules(product) == [("UNAUTHORIZED_URGENT_FIX", path)]
    critical(product, tmp_path, monkeypatch, comment(PERSON, COMMAND, BEFORE))
    assert rules(product) == []


def test_a_fix_that_is_not_critical_needs_no_authorization(product, tmp_path, monkeypatch):
    fix(product)
    framework = git_head(product / ".framework")
    found = [issue(12, "problem", problem(12, severity="high"))]
    path = write_host(tmp_path / "issues.json", tags={"v6.0.0": framework}, issues=found)
    monkeypatch.setenv("QF_HOST_FILE", str(path))
    assert rules(product) == []
