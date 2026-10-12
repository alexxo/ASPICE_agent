"""agent/resolve_stage_tool.py — the first stage that is not done, worked out from disk."""

import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone

from product_builder import STACK, baseline_requirements, build_product

from agent.read_stages_tool import flow_stages
from agent.record_checkpoint_tool import record_checkpoint
from agent.resolve_stage_tool import resolve_stage

NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)


def _approve_diagrams(root):
    record_checkpoint(root, 1, "approved", "Alex", "architect", now=NOW)


def test_requirements_without_an_approved_diagram_keep_the_product_at_stage_1(product):
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("diagram", "gates_failing")
    assert [f["rule"] for f in state["findings"]] == ["MISSING_APPROVAL"]


def test_a_diagram_without_requirements_awaits_checkpoint_1(tmp_path):
    root = build_product(tmp_path, requirements={})
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == ("diagram", "awaiting_checkpoint")


def test_with_approved_diagrams_and_good_requirements_it_awaits_checkpoint_2(product):
    _approve_diagrams(product)
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("requirements", "awaiting_checkpoint")
    assert state["done"] == ["diagram"]


def test_failing_gates_keep_the_product_at_stage_2(tmp_path):
    reqs = baseline_requirements()
    reqs["login"][0]["size"] = "XXL"
    root = build_product(tmp_path, requirements=reqs)
    _approve_diagrams(root)
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == ("requirements", "gates_failing")
    assert state["findings"][0]["rule"] == "SCHEMA_VIOLATION"


def _approve_requirements(root):
    _approve_diagrams(root)
    record_checkpoint(root, 2, "approved", "Alex", "architect", now=NOW.replace(hour=10))


def _stack_only(tmp_path):
    """Stack and decision record written, no component designed yet."""
    root = build_product(tmp_path, stack=STACK)
    (root / "docs/architecture/auth-flow.md").unlink()
    return root


def test_after_checkpoint_2_the_architecture_starts_with_the_stack(product):
    _approve_requirements(product)
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("architecture", "gates_failing")
    assert [f["rule"] for f in state["findings"]] == ["MISSING_STACK"]
    assert state["done"] == ["diagram", "requirements"]


def test_a_written_stack_awaits_checkpoint_3_before_any_component(tmp_path):
    root = _stack_only(tmp_path)
    _approve_requirements(root)
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == ("architecture", "awaiting_checkpoint")


def test_an_approved_stack_asks_for_the_components(tmp_path):
    root = _stack_only(tmp_path)
    _approve_requirements(root)
    record_checkpoint(root, 3, "approved", "Alex", "architect", now=NOW.replace(hour=11))
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == ("architecture", "gates_failing")
    assert [f["rule"] for f in state["findings"]] == ["NO_ARCHITECTURE"] * 2  # design + testability


def test_a_complete_architecture_moves_the_product_to_stage_4(tmp_path):
    root = build_product(tmp_path, stack=STACK)
    _approve_requirements(root)
    record_checkpoint(root, 3, "approved", "Alex", "architect", now=NOW.replace(hour=11))
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == ("detailed_design", "gates_failing")
    assert [f["rule"] for f in state["findings"]] == ["NO_DETAILED_DESIGN"]
    assert state["done"] == ["diagram", "requirements", "architecture"]


def test_components_designed_before_the_stack_was_approved_fail(tmp_path):
    root = build_product(tmp_path, stack=STACK)  # components already committed
    _approve_requirements(root)
    later = datetime(2099, 1, 1, tzinfo=timezone.utc)
    record_checkpoint(root, 3, "approved", "Alex", "architect", now=later)
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == ("architecture", "gates_failing")
    assert [f["rule"] for f in state["findings"]] == ["APPROVED_TOO_LATE"]


def test_planned_gates_are_reported_as_not_run(product, monkeypatch):
    stages = [
        replace(s, planned_gates=("a_planned_gate",)) if s.id == "requirements" else s
        for s in flow_stages()
    ]
    monkeypatch.setattr("agent.resolve_stage_tool.flow_stages", lambda: stages)
    _approve_requirements(product)
    state = resolve_stage(product)
    assert state["stage"] == "architecture"
    assert state["not_run"] == ["a_planned_gate"]


def test_a_changed_diagram_sends_the_product_back_to_stage_1(product):
    _approve_diagrams(product)
    spec = product / "docs/diagrams/login.sequence.json"
    spec.write_text(spec.read_text().replace("submit", "send"))
    assert resolve_stage(product)["stage"] == "diagram"


def test_an_invalid_config_stops_the_resolver(tmp_path):
    state = resolve_stage(tmp_path)
    assert state["status"] == "invalid_config"


def _check(repo_root, root):
    return subprocess.run(
        [
            sys.executable,
            str(repo_root / "agent/resolve_stage_tool.py"),
            "--root",
            str(root),
            "--check",
        ],
        capture_output=True,
        text=True,
        check=False,
    ).returncode


def test_check_fails_when_reached_gates_fail(repo_root, tmp_path):
    reqs = baseline_requirements()
    reqs["login"][0]["size"] = "XXL"
    root = build_product(tmp_path, requirements=reqs)
    _approve_diagrams(root)
    assert _check(repo_root, root) == 1


def test_check_passes_while_waiting_for_a_checkpoint(repo_root, product):
    _approve_diagrams(product)
    assert _check(repo_root, product) == 0


def test_check_passes_at_the_diagram_stage_without_requirements(repo_root, tmp_path):
    root = build_product(tmp_path, requirements={})
    assert _check(repo_root, root) == 0
