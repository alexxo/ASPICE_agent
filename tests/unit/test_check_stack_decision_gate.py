"""gates/swe/check_stack_decision_gate.py — the stack exists, is pinned, and has its decision."""

import copy

from product_builder import STACK, baseline_requirements, build_product

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


def test_a_stack_breaking_its_contract_is_reported(tmp_path):
    root = _stack(tmp_path, lambda s: s["language"].update(version="latest"))
    assert _rules(root) == ["INVALID_STACK"]


def test_a_missing_decision_record_is_reported(tmp_path):
    root = _stack(tmp_path, lambda s: s.update(decision_record="docs/decisions/0009-x.md"))
    assert _rules(root) == ["MISSING_DECISION_RECORD"]


def test_a_suite_named_by_a_requirement_but_missing_from_the_stack_is_reported(tmp_path):
    root = _stack(tmp_path, lambda s: s["suites"].pop("integration"))
    findings = check(read_product_config(root))
    assert {f.rule for f in findings} == {"UNKNOWN_INSTRUMENT"}
    assert all(f.file == "docs/requirements/login.md" for f in findings)


def test_a_bench_suite_is_required_only_if_a_requirement_names_it(tmp_path):
    reqs = baseline_requirements()
    next(r for r in reqs["login"] if r["uid"] == "REQ-0047")["measurement_method"]["instrument"] = (
        "bench"
    )
    root = build_product(tmp_path, requirements=reqs, stack=STACK, git=False)
    assert _rules(root) == ["UNKNOWN_INSTRUMENT"]
