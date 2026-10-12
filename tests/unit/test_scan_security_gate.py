"""gates/sup/scan_security_gate.py — no leaked secret, no vulnerable dependency, merged."""

import json

import pytest
from product_builder import build_python_product, commit_all, python_stack

from gates.sup.scan_security_gate import blocking, check
from tools.read_product_config_tool import read_product_config


@pytest.fixture(scope="module")
def stack():
    return python_stack()


@pytest.fixture
def product(tmp_path, stack):
    return build_python_product(tmp_path / "product", stack=stack)


def _found(product, kind, results):
    (product / f"scanners/{kind}.findings.json").write_text(json.dumps(results))
    commit_all(product, f"{kind} findings")


def _rules(product):
    return sorted(f.rule for f in check(read_product_config(product)))


def _result(rule="R1", severity=None, uri="src/auth_service/settings.py", line=3):
    result = {
        "ruleId": rule,
        "message": {"text": "found"},
        "locations": [
            {"physicalLocation": {"artifactLocation": {"uri": uri}, "region": {"startLine": line}}}
        ],
    }
    if severity is not None:
        result["properties"] = {"security-severity": severity}
    return result


def test_clean_scans_pass(product):
    assert _rules(product) == []


def test_a_leaked_secret_blocks_even_without_a_score(product):
    _found(product, "secrets", [_result("generic-api-key")])
    (finding,) = check(read_product_config(product))
    assert (finding.rule, finding.file, finding.line) == (
        "SECURITY_FINDING",
        "src/auth_service/settings.py",
        3,
    )
    assert "security_scans.secrets" in finding.message and "unscored" in finding.message


@pytest.mark.parametrize(("score", "blocks"), [("9.8", True), ("7.0", True), ("6.9", False)])
def test_a_dependency_blocks_from_high_up(product, score, blocks):
    _found(product, "dependencies", [_result("GHSA-1", score)])
    assert _rules(product) == (["SECURITY_FINDING"] if blocks else [])


LOW = {"security-severity": "3.1"}


def test_the_rules_score_counts_when_the_result_has_none():
    sarif = {
        "runs": [
            {
                "tool": {"driver": {"rules": [{"id": "low", "properties": LOW}]}},
                "results": [_result("low"), _result("high", "8.1")],
            }
        ]
    }
    assert [text.split(" ")[0] for _, _, text in blocking(sarif)] == ["high"]


def test_a_scanner_that_writes_nothing_did_not_run(tmp_path, stack):
    broken = json.loads(json.dumps(stack))
    broken["security_scans"]["secrets"]["run"] = "true"
    product = build_python_product(tmp_path / "broken", stack=broken)
    assert _rules(product) == ["SCAN_NOT_RUN"]


def test_a_scanner_of_another_version_is_caught(tmp_path, stack):
    other = json.loads(json.dumps(stack))
    other["security_scans"]["dependencies"]["version"] = "2.0.0"
    product = build_python_product(tmp_path / "other", stack=other)
    assert _rules(product) == ["TOOL_VERSION_MISMATCH"]
