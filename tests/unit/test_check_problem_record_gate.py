"""gates/sup/check_problem_record_gate.py — every problem recorded, analysed, announced."""

import json

import pytest
from product_builder import (
    build_releasable_product,
    commit_all,
    git_head,
    issue,
    problem,
    problem_report,
    propose_release,
    write_host,
    write_problem_test,
)

from agent.read_stages_tool import read_stages
from gates.sup.check_problem_record_gate import GATE, check
from tools.read_product_config_tool import read_product_config


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


def test_gate_name_follows_the_convention():
    assert GATE == "check_problem_record_gate"


def test_without_a_fix_or_a_release_no_problem_is_read(product, tmp_path, monkeypatch):
    issues(product, tmp_path, monkeypatch, issue(12, "problem", None))
    assert rules(product) == []


def test_a_problem_being_fixed_must_be_recorded_and_analysed(product, tmp_path, monkeypatch):
    write_problem_test(product, 12)
    write_problem_test(product, 13)
    commit_all(product, "test: reproduce #12 and #13")
    issues(
        product,
        tmp_path,
        monkeypatch,
        issue(12, "problem", None),
        issue(13, "problem", problem(13, status="open", cause=None, severity=None)),
        issue(14, "problem", None),  # nobody fixes it yet
    )
    assert rules(product) == [
        ("INCOMPLETE_PROBLEM_RECORD", "#12"),
        ("MISSING_ANALYSIS", "#13"),
    ]


def test_an_analysed_problem_being_fixed_passes(product, tmp_path, monkeypatch):
    write_problem_test(product, 12)
    commit_all(product, "test: reproduce #12")
    issues(product, tmp_path, monkeypatch, issue(12, "problem", problem(12)))
    assert rules(product) == []


def test_at_release_every_problem_is_checked(product, tmp_path, monkeypatch):
    propose_release(product)
    issues(
        product,
        tmp_path,
        monkeypatch,
        issue(12, "problem", None),
        issue(13, "problem", problem(13, cause=None, escape=None)),
        issue(14, "problem", problem(14, status="open", cause=None, impact=None, severity=None)),
        issue(15, "problem", problem(15, severity="critical")),
        issue(
            16,
            "problem",
            problem(16, severity="high", affected_parties=["support"], notified="2026-10-12"),
        ),
    )
    assert rules(product) == [
        ("INCOMPLETE_PROBLEM_RECORD", "#12"),
        ("MISSING_ALERT", "#15"),
        ("MISSING_ANALYSIS", "#13"),
    ]


def test_the_analysis_names_where_the_defect_came_in_and_got_through(
    product, tmp_path, monkeypatch
):
    write_problem_test(product, 12)
    write_problem_test(product, 13)
    commit_all(product, "test: reproduce #12 and #13")
    issues(
        product,
        tmp_path,
        monkeypatch,
        issue(12, "problem", problem(12, origin=None)),
        issue(13, "problem", problem(13, escape={"stage": "unit_testing", "why": "none"})),
    )
    found = {f.file: f for f in check(read_product_config(product))}
    assert found["#12"].rule == "MISSING_ANALYSIS" and "origin" in found["#12"].message
    assert found["#13"].rule == "INCOMPLETE_PROBLEM_RECORD"
    assert "escape" in found["#13"].message


def test_a_report_from_the_form_waits_for_its_analysis(product, tmp_path, monkeypatch):
    propose_release(product)
    write_problem_test(product, 13)
    commit_all(product, "test: reproduce #13")
    issues(
        product,
        tmp_path,
        monkeypatch,
        problem_report(12),
        problem_report(13),  # a test names it: it is being fixed
        problem_report(14, state="closed", closed="2099-01-02T09:00:00Z"),
    )
    assert rules(product) == [
        ("INCOMPLETE_PROBLEM_RECORD", "#13"),
        ("INCOMPLETE_PROBLEM_RECORD", "#14"),
    ]


def test_origin_and_escape_name_the_stages_of_the_manifest(repo_root):
    schema = json.loads((repo_root / "contracts/problem_contract.v1.schema.json").read_text())
    assert schema["$defs"]["stage"]["enum"] == [s.id for s in read_stages()]
