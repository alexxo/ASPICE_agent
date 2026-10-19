"""gates/swe/check_stack_decision_gate.py — the stack is pinned, complete and decided."""

import copy

from product_builder import STACK, build_product

from gates.swe.check_stack_decision_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _stack(tmp_path, change):
    stack = copy.deepcopy(STACK)
    change(stack)
    return build_product(tmp_path, stack=stack, git=False)


def test_gate_name_follows_the_convention():
    assert GATE == "check_stack_decision_gate"


def test_a_complete_stack_passes(tmp_path):
    assert _rules(build_product(tmp_path, stack=STACK, git=False)) == []


def test_a_missing_stack_is_reported(tmp_path):
    assert _rules(build_product(tmp_path, git=False)) == ["MISSING_STACK"]


def _row(stack, area):
    return next(r for r in stack["areas"] if r["area"] == area)


def test_a_stack_breaking_its_contract_is_reported(tmp_path):
    root = _stack(tmp_path, lambda s: _row(s, "language").update(version="latest"))
    assert _rules(root) == ["INVALID_STACK"]


def test_a_missing_decision_record_is_reported(tmp_path):
    root = _stack(tmp_path, lambda s: s.update(decision_record="docs/decisions/0009-x.md"))
    assert _rules(root) == ["MISSING_DECISION_RECORD"]


def test_an_area_without_a_row_is_reported(tmp_path):
    root = _stack(tmp_path, lambda s: s["areas"].remove(_row(s, "llm")))
    findings = check(read_product_config(root))
    assert [f.rule for f in findings] == ["MISSING_STACK_AREA"]
    assert "'llm'" in findings[0].message


def test_an_area_with_several_tools_and_a_product_area_pass(tmp_path):
    def change(stack):
        stack["areas"].remove(_row(stack, "libraries"))
        stack["areas"] += [
            {"area": "libraries", "tool": "jackson", "version": "2.17.2"},
            {"area": "libraries", "tool": "slf4j", "version": "2.0.16"},
            {"area": "message_broker", "tool": "rabbitmq", "version": "3.13.7"},
        ]

    assert _rules(_stack(tmp_path, change)) == []


def test_an_area_not_needed_without_a_reason_is_reported(tmp_path):
    root = _stack(tmp_path, lambda s: _row(s, "llm").update(not_needed="  "))
    assert _rules(root) == ["MISSING_REASON"]


def test_an_area_the_gates_run_cannot_be_struck_off(tmp_path):
    def change(stack):
        stack["areas"].remove(_row(stack, "lint"))
        stack["areas"].append({"area": "lint", "not_needed": "the team reads carefully"})

    findings = check(read_product_config(_stack(tmp_path, change)))
    assert [f.rule for f in findings] == ["MISSING_STACK_AREA"]
    assert "'lint'" in findings[0].message


def test_an_area_the_framework_gives_must_name_its_tool(tmp_path):
    def change(stack):
        _row(stack, "ci_cd").update(tool="GitLab CI")
        _row(stack, "diagram_tool").update(tool="mermaid")

    findings = check(read_product_config(_stack(tmp_path, change)))
    assert [f.rule for f in findings] == ["GIVEN_AREA_MISMATCH"] * 2
    assert "'GitHub Actions'" in findings[0].message
    assert "'archify'" in findings[1].message


def test_a_given_tool_matches_but_for_case_and_punctuation(tmp_path):
    root = _stack(tmp_path, lambda s: _row(s, "ci_cd").update(tool="github-actions"))
    assert _rules(root) == []


def test_an_area_the_framework_gives_cannot_be_struck_off(tmp_path):
    def change(stack):
        stack["areas"].remove(_row(stack, "version_control"))
        stack["areas"].append({"area": "version_control", "not_needed": "no history"})

    assert _rules(_stack(tmp_path, change)) == ["GIVEN_AREA_MISMATCH"]
