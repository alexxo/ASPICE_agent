"""agent/resolve_stage_tool.py — with the real gates, what the routing tests cannot stand in for.

The routing for every stage is test_resolve_stage_routing.py's; these keep the
real gates and files: the --check exit code, the approvals read from disk, and
the gates not run.
"""

import subprocess
import sys
from dataclasses import replace

from product_builder import approve_checkpoint, baseline_requirements, build_product

from agent.read_stages_tool import flow_stages
from agent.resolve_stage_tool import resolve_stage


def _approve_diagrams(root):
    approve_checkpoint(root, 1)


def test_a_diagram_without_requirements_awaits_checkpoint_1(tmp_path):
    root = build_product(tmp_path, requirements={})
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == ("diagram", "awaiting_checkpoint")


def _approve_requirements(root):
    _approve_diagrams(root)
    approve_checkpoint(root, 2)


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


def _change_the_approved_diagram(root):
    spec = root / "docs/diagrams/login.sequence.json"
    spec.write_text(spec.read_text().replace("submit", "send"))


def _rules(found):
    return {f["rule"] for f in found}


def test_a_changed_approved_diagram_fails_off_its_checkpoint_branch(product, monkeypatch):
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    _approve_diagrams(product)
    _change_the_approved_diagram(product)
    state = resolve_stage(product)
    assert state["status"] == "gates_failing"
    assert "APPROVAL_OUTDATED" in _rules(state["findings"])


def test_on_its_checkpoint_branch_the_approval_waits_for_the_merge(product, monkeypatch):
    """FB-72: the merge of checkpoint/1 is the approval, so its pull request cannot
    wait to be green until it merged."""
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    _approve_diagrams(product)
    subprocess.run(["git", "-C", str(product), "checkout", "-q", "-b", "checkpoint/1"], check=True)
    _change_the_approved_diagram(product)
    state = resolve_stage(product)
    assert "APPROVAL_OUTDATED" in _rules(state["reported"])
    assert not _rules(state["findings"]) & {"MISSING_APPROVAL", "APPROVAL_OUTDATED"}
    monkeypatch.setenv("GITHUB_HEAD_REF", "checkpoint/1")  # CI reads the pull request's branch
    subprocess.run(["git", "-C", str(product), "checkout", "-q", "-b", "elsewhere"], check=True)
    assert "APPROVAL_OUTDATED" in _rules(resolve_stage(product)["reported"])


def test_on_its_checkpoint_branch_the_other_findings_still_fail(product, monkeypatch):
    monkeypatch.setenv("GITHUB_HEAD_REF", "checkpoint/2")
    _approve_requirements(product)
    login = product / "docs/requirements/login.md"
    login.write_text(login.read_text().replace("size: S", "size: XXL", 1))
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("requirements", "gates_failing")
    assert state["findings"] and not _rules(state["findings"]) & {"APPROVAL_OUTDATED"}
