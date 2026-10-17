"""Scenario — the SWE.2 architecture stage end to end, on a copy of the example product.

The product starts where the SWE.1 scenario ends: requirements derived and
approved at checkpoint 2. The loop of agent/run_aspice_agent.md is driven with
the agent's own tools; each attempt copies a scripted plugin output
(tests/scenarios/plugin_outputs/architecture/) into the product. The stage has
its checkpoint inside it: the stack is written and approved at checkpoint 3
before any component is designed.

- the stack is approved, the design passes the gates, and the product moves on;
- a broken design is caught and fixed by a retry;
- changes requested at checkpoint 3 keep the product waiting, with no component;
- a stack changed after its approval withdraws it.
"""

import shutil
from datetime import datetime, timezone

from product_builder import commit_all

from agent.count_retries_tool import decide, record_attempt
from agent.load_skills_tool import load_skills
from agent.read_stages_tool import stage
from agent.record_checkpoint_tool import record_checkpoint
from agent.record_stage_done_tool import record_stage_done
from agent.render_review_tool import render_review
from agent.resolve_stage_tool import resolve_stage
from agent.run_gates_tool import reached_gates, run_gates

OUTPUTS = "tests/scenarios/plugin_outputs"
APPROVED = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


def _write(repo_root, product, output):
    """The plugin writes its files where the product keeps them."""
    shutil.copytree(repo_root / OUTPUTS / output, product, dirs_exist_ok=True)


def _requirements_approved(repo_root, product):
    """Where the SWE.1 scenario ends: requirements derived and approved."""
    target = product / "docs" / "requirements" / "login.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(repo_root / OUTPUTS / "requirements" / "correct" / "login.md", target)
    render_review(product)
    record_checkpoint(product, 2, "approved", "Example Architect", "architect", now=APPROVED)
    commit_all(product, "requirements approved at checkpoint 2")


def _stack_written(repo_root, product):
    """Steps 3–7 up to checkpoint 3: the stack and its decision record."""
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("architecture", "in_progress")
    assert [f["rule"] for f in state["reported"]] == ["MISSING_STACK"]
    assert state["done"] == ["diagram", "requirements"]

    loaded = load_skills(product, "architecture")
    assert loaded["plugin"]["skill_file"].endswith(
        "plugins/swe/derive_architecture_plugin/SKILL.md"
    )
    assert len(loaded["framework_skills"]) == 5

    _write(repo_root, product, "architecture/stack")
    decision = _attempts(repo_root, product, [])
    assert decision["decision"] == "pass"
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("architecture", "awaiting_checkpoint")


def _stack_approved(repo_root, product):
    _requirements_approved(repo_root, product)
    _stack_written(repo_root, product)
    record_checkpoint(product, 3, "approved", "Example Architect", "architect")
    commit_all(product, "stack approved at checkpoint 3")
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("architecture", "in_progress")
    assert [f["rule"] for f in state["reported"]] == ["NO_ARCHITECTURE"] * 2  # design + testability


def _attempts(repo_root, product, outputs):
    """The plugin writes, the gates the stage has reached judge, the counter decides."""
    architecture = stage("architecture")
    for output in outputs or [None]:
        if output:
            _write(repo_root, product, f"architecture/{output}")
        results = run_gates(product, reached_gates(product, architecture))
        record_attempt(product, "architecture", results)
        decision = decide(product, "architecture")
        if decision["decision"] != "retry":
            break
    return decision


def _rules(product, number):
    import json

    log = product / ".qf/attempts/architecture" / f"attempt-{number}.json"
    return sorted(f["rule"] for gate in json.loads(log.read_text()) for f in gate["findings"])


def test_an_approved_stack_and_a_passing_design_move_the_product_on(repo_root, product):
    _stack_approved(repo_root, product)
    decision = _attempts(repo_root, product, ["correct"])
    assert decision["decision"] == "pass"
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("architecture", "in_progress")
    assert "record_stage_done_tool" in state["reason"]
    commit_all(product, "architecture designed")
    record_stage_done(product, "architecture")
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("detailed_design", "in_progress")
    assert [f["rule"] for f in state["reported"]] == ["NO_DETAILED_DESIGN"]
    assert state["done"] == ["diagram", "requirements", "architecture"]


def test_a_broken_design_is_caught_and_fixed_by_a_retry(repo_root, product):
    _stack_approved(repo_root, product)
    attempts_before = len(list((product / ".qf/attempts/architecture").glob("*.json")))
    decision = _attempts(repo_root, product, ["broken", "correct"])
    assert decision["decision"] == "pass"
    first = attempts_before + 1
    assert _rules(product, first) == [
        "EXTERNAL_MISMATCH",
        "UNKNOWN_REQUIREMENT",
        "UNMET_REQUIREMENT",
    ]
    assert _rules(product, first + 1) == []


def test_changes_requested_at_checkpoint_3_keep_the_product_waiting(repo_root, product):
    _requirements_approved(repo_root, product)
    _stack_written(repo_root, product)
    record_checkpoint(
        product,
        3,
        "changes-requested",
        "Example Architect",
        "architect",
        "Pin the Maven wrapper, not a system Maven.",
    )
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("architecture", "awaiting_checkpoint")
    assert "Pin the Maven wrapper" in state["reason"]
    assert not (product / "docs/architecture/auth-flow.md").exists()


def test_a_stack_changed_after_its_approval_withdraws_it(repo_root, product):
    _stack_approved(repo_root, product)
    _attempts(repo_root, product, ["correct"])
    stack = product / "docs" / "architecture" / "stack.yaml"
    stack.write_text(stack.read_text().replace('version: "3.3.4"', 'version: "3.4.0"'))
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("architecture", "awaiting_checkpoint")
    assert "docs/architecture/stack.yaml" in state["reason"]
