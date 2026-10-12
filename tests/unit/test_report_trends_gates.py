"""gates/sup/report_problem_trends_gate.py, report_quality_trends_gate.py — the release
reports its problems and its faults left open."""

import json

import pytest
from product_builder import (
    build_releasable_product,
    git_head,
    issue,
    problem,
    propose_release,
    write_host,
)

from gates.sup import report_problem_trends_gate, report_quality_trends_gate
from tools.read_product_config_tool import read_product_config
from tools.write_verification_report_tool import PAGE, write_report

GATES = (report_problem_trends_gate, report_quality_trends_gate)


@pytest.fixture
def product(tmp_path, monkeypatch):
    root, _host = build_releasable_product(tmp_path)
    framework = git_head(root / ".framework")
    found = [
        issue(12, "problem", problem(12, severity="high")),
        issue(13, "problem", problem(13, status="closed"), state="closed",
              closed="2099-01-02T09:00:00Z"),
        issue(1, "non-conformance", {"found_in": 3}, labels=["escalated"]),
    ]  # fmt: skip
    path = write_host(tmp_path / "issues.json", tags={"v6.0.0": framework}, issues=found)
    monkeypatch.setenv("QF_HOST_FILE", str(path))
    return root


def findings(root):
    config = read_product_config(root)
    return [(g.GATE, f.rule) for g in GATES for f in g.check(config)]


def test_gate_names_follow_the_convention():
    assert [g.GATE for g in GATES] == ["report_problem_trends_gate", "report_quality_trends_gate"]


def test_without_a_release_there_is_nothing_to_count(product):
    write_report(read_product_config(product))
    assert findings(product) == []


def test_a_release_report_counts_the_problems_and_the_faults(product):
    propose_release(product)
    written = write_report(read_product_config(product))
    report = json.loads(written.read_text())
    assert report["problems"] == {
        "since": None,
        "opened": 2,
        "fixed": 1,
        "open": 1,
        "by_severity": {"high": 1, "medium": 1},
        "by_component": {"auth-service": 2},
    }
    assert report["quality"] == {"since": None, "opened": 1, "closed": 0, "escalated": 1}
    assert "## Problems since the start" in written.with_name(PAGE).read_text()
    assert findings(product) == []


def test_a_release_report_without_the_sections_is_reported(product):
    propose_release(product)
    written = write_report(read_product_config(product))
    report = json.loads(written.read_text())
    del report["problems"], report["quality"]
    written.write_text(json.dumps(report))
    assert findings(product) == [
        ("report_problem_trends_gate", "MISSING_TREND_SECTION"),
        ("report_quality_trends_gate", "MISSING_TREND_SECTION"),
    ]
