"""agent/resolve_stage_tool.py — with the real gates, what the routing tests cannot stand in for.

The routing for every stage is test_resolve_stage_routing.py's; these keep the
real gates and files: the --check exit code, the approvals read from disk, and
the gates not run.
"""

import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone

from product_builder import baseline_requirements, build_product

from agent.read_stages_tool import flow_stages
from agent.record_checkpoint_tool import record_checkpoint
from agent.resolve_stage_tool import resolve_stage

NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)


def _approve_diagrams(root):
    record_checkpoint(root, 1, "approved", "Alex", "architect", now=NOW)


def test_a_diagram_without_requirements_awaits_checkpoint_1(tmp_path):
    root = build_product(tmp_path, requirements={})
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == ("diagram", "awaiting_checkpoint")


def _approve_requirements(root):
    _approve_diagrams(root)
    record_checkpoint(root, 2, "approved", "Alex", "architect", now=NOW.replace(hour=10))


def test_planned_gates_are_reported_as_not_run(product, monkeypatch):
    stages = [
        replace(s, planned_gates=("a_planned_gate",)) if s.id == "requirements" else s
        for s in flow_stages()
    ]
    monkeypatch.setattr("agent.resolve_stage_tool.flow_stages", lambda: stages)
    _approve_requirements(product)
    state = resolve_stage(product)
    assert state["stage"] == "architecture"
    assert {"gate": "a_planned_gate", "reason": "planned"} in state["not_run"]


def test_the_gates_of_stages_not_reached_are_reported_as_not_run(product):
    _approve_diagrams(product)
    not_run = resolve_stage(product)["not_run"]
    assert {"gate": "check_detailed_design_contract_gate", "reason": "stage_not_reached"} in not_run
    assert {"gate": "check_glossary_gate", "reason": "stage_not_reached"} not in not_run


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


def test_check_passes_while_the_current_stage_is_in_progress(repo_root, tmp_path):
    reqs = baseline_requirements()
    reqs["login"][0]["size"] = "XXL"
    root = build_product(tmp_path, requirements=reqs)
    _approve_diagrams(root)
    assert _check(repo_root, root) == 0


def test_check_fails_when_a_finished_stage_fails(repo_root, product):
    _approve_requirements(product)
    login = product / "docs/requirements/login.md"
    login.write_text(login.read_text().replace("size: S", "size: XXL", 1))
    assert _check(repo_root, product) == 1


def test_check_passes_when_an_approval_moves_the_product_to_an_empty_stage(repo_root, tmp_path):
    root = build_product(tmp_path, requirements={})
    _approve_diagrams(root)  # the approval is committed with stage 1's work (FB-15)
    assert resolve_stage(root)["status"] == "in_progress"
    assert _check(repo_root, root) == 0
