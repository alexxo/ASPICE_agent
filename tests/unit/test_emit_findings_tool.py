"""tools/emit_findings_tool.py — prints a gate result in findings.v1."""

import io
import json

import pytest

from tools.emit_findings_tool import Finding, emit, result
from tools.validate_contract_tool import validate

GATE = "check_glossary_gate"


def _emit(findings):
    out = io.StringIO()
    code = emit(GATE, findings, out)
    return code, json.loads(out.getvalue())


def test_no_findings_is_a_pass_with_exit_code_0():
    code, doc = _emit([])
    assert code == 0
    assert doc == {"gate": GATE, "result": "pass", "findings": []}


def test_findings_are_a_fail_with_exit_code_1():
    code, doc = _emit(
        [
            Finding(
                "UNDEFINED_TERM", "docs/requirements/login.md", 12, "Term _session_ is not defined."
            )
        ]
    )
    assert code == 1
    assert doc["result"] == "fail"
    assert doc["findings"] == [
        {
            "gate": GATE,
            "rule": "UNDEFINED_TERM",
            "file": "docs/requirements/login.md",
            "line": 12,
            "message": "Term _session_ is not defined.",
        }
    ]


def test_findings_come_in_a_fixed_order():
    findings = [
        Finding("UNUSED_TERM", "docs/glossary.md", None, "b"),
        Finding("UNDEFINED_TERM", "docs/requirements/login.md", 30, "c"),
        Finding("UNDEFINED_TERM", "docs/requirements/login.md", 12, "a"),
    ]
    _, doc = _emit(findings)
    assert [(f["file"], f["line"]) for f in doc["findings"]] == [
        ("docs/glossary.md", None),
        ("docs/requirements/login.md", 12),
        ("docs/requirements/login.md", 30),
    ]


def test_output_follows_the_findings_contract():
    doc = result(
        GATE, [Finding("UNUSED_TERM", "docs/glossary.md", None, "Term account is unused.")]
    )
    assert validate(doc, "findings") == []


def test_a_finding_that_breaks_the_contract_is_refused():
    with pytest.raises(ValueError):
        result(GATE, [Finding("undefined term", "docs/glossary.md", 0, "")])


def test_a_gate_name_outside_the_convention_is_refused():
    with pytest.raises(ValueError):
        result("glossary-gate", [])
