"""agent/resolve_stage_tool.py — the routing alone, with the gates and the records stood in.

The gates' own rules are their unit tests' to prove, and a real walk through the
stages is the journey's; here the resolver's decisions are checked for every
stage of the flow in milliseconds: which stage is current, and whether its
findings fail, are reported, or wait for a seal.
"""

from types import SimpleNamespace

import pytest

from agent import resolve_stage_tool as resolver
from agent.read_stages_tool import always_gates, flow_stages, host_gates

FLOW = [s.id for s in flow_stages()]


@pytest.fixture
def world(monkeypatch):
    """Every gate passes, every checkpoint is approved and every stage recorded,
    until a test says otherwise."""
    state = SimpleNamespace(
        failing={},  # gate → the rule IDs it reports
        unapproved=set(),  # checkpoints without a current approval
        approved_once=set(),  # of those, the ones approved before
        unrecorded=set(),  # stage ids without a stage done record
        releasing=False,
        host=True,
        ran=[],
    )

    def run_gates(root, gates):
        state.ran += list(gates)
        return [
            {
                "gate": g,
                "result": "fail" if g in state.failing else "pass",
                "findings": [
                    {"rule": r, "file": ".", "line": None, "message": r}
                    for r in state.failing.get(g, ())
                ],
            }
            for g in gates
        ]

    def current_approval(config, checkpoint, approves):
        if checkpoint in state.unapproved:
            return None, "no current approval"
        return object(), ""

    monkeypatch.setattr(resolver, "read_product_config", lambda root: SimpleNamespace(root=root))
    monkeypatch.setattr(resolver, "run_gates", run_gates)
    monkeypatch.setattr(resolver, "current_approval", current_approval)
    monkeypatch.setattr(
        resolver, "checkpoint_due", lambda c, approves: approves != "release" or state.releasing
    )
    monkeypatch.setattr(resolver, "ever_approved", lambda c, n, a: n in state.approved_once)
    monkeypatch.setattr(
        resolver,
        "stage_done_record",
        lambda c, sid, n: None if sid in state.unrecorded else object(),
    )
    monkeypatch.setattr(resolver, "pending", lambda c: ["1.0.0"] if state.releasing else [])
    monkeypatch.setattr(resolver, "host_configured", lambda: state.host)
    return state


def _resolve(tmp_path):
    return resolver.resolve_stage(tmp_path)


def test_with_everything_passing_the_flow_is_complete(world, tmp_path):
    state = _resolve(tmp_path)
    assert (state["stage"], state["status"]) == (None, "complete")
    assert state["done"] == FLOW


@pytest.mark.parametrize(("checkpoint", "stage"), [(1, "diagram"), (2, "requirements")])
def test_an_unapproved_checkpoint_stops_its_stage(world, tmp_path, checkpoint, stage):
    world.unapproved = {checkpoint}
    state = _resolve(tmp_path)
    assert (state["stage"], state["status"]) == (stage, "awaiting_checkpoint")


def test_the_stack_approval_comes_before_the_component_gates(world, tmp_path):
    world.unapproved = {3}
    state = _resolve(tmp_path)
    assert (state["stage"], state["status"]) == ("architecture", "awaiting_checkpoint")
    stage = next(s for s in flow_stages() if s.id == "architecture")
    assert not set(stage.gates_after_checkpoint) & set(world.ran)
    assert {g["gate"] for g in state["not_run"]} >= set(stage.gates_after_checkpoint)


@pytest.mark.parametrize("stage", ["detailed_design", "unit_construction", "software_verification"])
def test_the_current_stage_reports_its_findings(world, tmp_path, stage):
    earlier = set()
    for s in flow_stages():
        if s.id == stage:
            break
        earlier |= {*s.gates, *s.gates_after_checkpoint}
    gate = next(
        g for g in next(s for s in flow_stages() if s.id == stage).gates if g not in earlier
    )
    world.failing = {gate: ["SOME_RULE"]}
    world.unrecorded = {stage}
    state = _resolve(tmp_path)
    assert (state["stage"], state["status"]) == (stage, "in_progress")
    assert state["findings"] == [] and [f["rule"] for f in state["reported"]] == ["SOME_RULE"]


def test_a_finished_stage_that_breaks_fails(world, tmp_path):
    world.failing = {"verify_code_to_design_link_gate": ["UNIT_OUTSIDE_COMPONENT"]}
    state = _resolve(tmp_path)
    assert (state["stage"], state["status"]) == ("unit_construction", "gates_failing")


def test_a_stage_approved_once_stays_enforced(world, tmp_path):
    world.failing = {"check_requirements_contract_gate": ["MISSING_FIELD"]}
    world.unapproved, world.approved_once = {2}, {2}
    state = _resolve(tmp_path)
    assert (state["stage"], state["status"]) == ("requirements", "gates_failing")


def test_while_a_release_is_proposed_every_stage_is_enforced(world, tmp_path):
    world.failing = {"verify_log_events_gate": ["MISSING_LOG_TEST"]}
    world.unrecorded = {"integration_verification"}
    world.releasing = True
    state = _resolve(tmp_path)
    assert (state["stage"], state["status"]) == ("integration_verification", "gates_failing")


def test_a_passing_stage_without_its_record_asks_for_it(world, tmp_path):
    world.unrecorded = {"detailed_design"}
    state = _resolve(tmp_path)
    assert (state["stage"], state["status"]) == ("detailed_design", "in_progress")
    assert "record_stage_done_tool.py --stage detailed_design" in state["reason"]


def test_a_pull_request_a_person_reviews_waits_for_them(world, tmp_path):
    world.failing = {"verify_delivery_reviewed_gate": [resolver.HOST_APPROVAL]}
    state = _resolve(tmp_path)
    assert state["status"] == "awaiting_checkpoint"
    assert [f["rule"] for f in state["findings"]] == [resolver.HOST_APPROVAL]


def test_unanswered_review_items_still_wait_for_the_person(world, tmp_path):
    world.failing = {
        "verify_delivery_reviewed_gate": [resolver.HOST_APPROVAL, "REVIEW_ITEMS_UNANSWERED"]
    }
    assert _resolve(tmp_path)["status"] == "awaiting_checkpoint"


def test_a_missing_review_beside_the_person_fails(world, tmp_path):
    world.failing = {
        "verify_delivery_reviewed_gate": ["MISSING_AGENT_REVIEW", resolver.HOST_APPROVAL]
    }
    assert _resolve(tmp_path)["status"] == "gates_failing"


def test_a_release_waits_for_the_customer(world, tmp_path):
    world.failing = {"verify_release_evidence_gate": [resolver.CUSTOMER_DECISION]}
    world.unapproved = {5}
    world.releasing = True
    state = _resolve(tmp_path)
    assert (state["stage"], state["status"]) == ("validation", "awaiting_checkpoint")


def test_without_a_host_the_host_gates_are_not_run(world, tmp_path):
    world.host = False
    state = _resolve(tmp_path)
    assert not set(host_gates()) & set(world.ran)
    no_host = {g["gate"] for g in state["not_run"] if g["reason"] == "no_host"}
    assert no_host == set(host_gates()) and set(always_gates()) - no_host <= set(world.ran)


def test_an_event_stage_breaking_after_the_flow_fails(world, tmp_path):
    world.failing = {"check_problem_record_gate": ["MISSING_ANALYSIS"]}
    state = _resolve(tmp_path)
    assert (state["stage"], state["status"]) == ("problem_resolution", "gates_failing")
