"""Scenario — the SWE.1 stage end to end, on a copy of the example product.

The loop of agent/run_aspice_agent.md is driven step by step with the agent's
own tools. The only thing replaced is the LLM doing the work: each attempt
copies a scripted plugin output (tests/scenarios/plugin_outputs/) into the
product, as the plugin would write it. The three outcomes the implementation
strategy asks for:

- a plugin produces requirements that pass the gates, and checkpoint 2 moves
  the product on;
- a broken requirement is caught and fixed by a retry;
- a stuck one reaches the architect after the first run and 3 retries.
"""

import json
import shutil
from datetime import datetime, timezone

from agent.count_retries_tool import decide, record_attempt
from agent.load_skills_tool import load_skills
from agent.read_config_tool import read_config
from agent.read_stages_tool import stage
from agent.record_checkpoint_tool import record_checkpoint
from agent.render_review_tool import render_review
from agent.resolve_stage_tool import resolve_stage
from agent.run_gates_tool import run_gates

OUTPUTS = "tests/scenarios/plugin_outputs/requirements"


def _start(product):
    """Steps 1–3 of the orchestrator, up to the work."""
    config, problems = read_config(product)
    assert problems == [] and config is not None

    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("requirements", "in_progress")
    assert state["done"] == ["diagram"]
    assert "NO_REQUIREMENTS" in {f["rule"] for f in state["reported"]}
    assert state["findings"] == []  # work in progress does not fail CI

    loaded = load_skills(product, "requirements")
    assert loaded["plugin"]["name"] == "quality-framework/derive_requirements_plugin"
    assert loaded["plugin"]["skill_file"].endswith(
        "plugins/swe/derive_requirements_plugin/SKILL.md"
    )
    assert len(loaded["framework_skills"]) == 3


def _attempts(repo_root, product, outputs):
    """Step 3–4 repeated: the plugin writes, the agent renders the review page, the
    gates judge, the counter decides."""
    decision = None
    for output in outputs:
        target = product / "docs" / "requirements" / "login.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(repo_root / OUTPUTS / output / "login.md", target)
        render_review(product, 2)
        results = run_gates(product, stage("requirements").gates)
        record_attempt(product, "requirements", results)
        decision = decide(product, "requirements")
        if decision["decision"] != "retry":
            break
    return decision


def _attempt_rules(product, number):
    log = product / ".qf/attempts/requirements" / f"attempt-{number}.json"
    return sorted(f["rule"] for gate in json.loads(log.read_text()) for f in gate["findings"])


def test_requirements_that_pass_the_gates_move_on_after_checkpoint_2(repo_root, product):
    _start(product)
    decision = _attempts(repo_root, product, ["correct"])
    assert (decision["decision"], decision["attempts"]) == ("pass", 1)

    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("requirements", "awaiting_checkpoint")

    now = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
    record_checkpoint(product, 2, "approved", "Example Architect", "architect", now=now)
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("architecture", "in_progress")
    assert state["reported"][0]["rule"] == "MISSING_STACK"
    assert state["done"] == ["diagram", "requirements"]


def test_a_broken_requirement_is_caught_and_fixed_by_a_retry(repo_root, product):
    _start(product)
    decision = _attempts(repo_root, product, ["broken", "correct"])
    assert (decision["decision"], decision["attempts"]) == ("pass", 2)
    assert _attempt_rules(product, 1) == ["MISSING_OBSERVABILITY", "UNMARKED_TERM"]
    assert _attempt_rules(product, 2) == []


def test_a_stuck_requirement_reaches_the_architect(repo_root, product):
    _start(product)
    decision = _attempts(repo_root, product, ["stuck"] * 5)
    assert (decision["decision"], decision["attempts"]) == ("escalate", 4)
    report = (product / decision["escalation_report"]).read_text()
    assert report.count("UNKNOWN_ELEMENT") == 4
    assert report.count("## Attempt") == 4
    assert resolve_stage(product)["status"] == "in_progress"


def test_changes_requested_at_checkpoint_2_keep_the_product_waiting(repo_root, product):
    _start(product)
    _attempts(repo_root, product, ["correct"])
    now = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
    record_checkpoint(
        product,
        2,
        "changes-requested",
        "Example Architect",
        "architect",
        "REQ-0014 should name the protocol.",
        now=now,
    )
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("requirements", "awaiting_checkpoint")
    assert "REQ-0014 should name the protocol." in state["reason"]


def test_editing_approved_requirements_withdraws_the_approval(repo_root, product):
    _start(product)
    _attempts(repo_root, product, ["correct"])
    now = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
    record_checkpoint(product, 2, "approved", "Example Architect", "architect", now=now)
    login = product / "docs" / "requirements" / "login.md"
    login.write_text(login.read_text().replace("five consecutive", "three consecutive"))
    render_review(product, 2)  # the agent renders the page again after every change
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("requirements", "awaiting_checkpoint")
    assert "docs/requirements/login.md" in state["reason"]


def test_a_changed_diagram_sends_the_product_back_to_stage_1(repo_root, product):
    """Requirements derived and approved; then the diagram changes. The checkpoint-1
    approval no longer covers it, nor do its picture and review page, so the product
    is back at the diagram stage."""
    _start(product)
    _attempts(repo_root, product, ["correct"])
    now = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
    record_checkpoint(product, 2, "approved", "Example Architect", "architect", now=now)
    assert resolve_stage(product)["stage"] == "architecture"

    spec = product / "docs" / "diagrams" / "login.sequence.json"
    spec.write_text(spec.read_text().replace("session opened", "session started"))
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("diagram", "gates_failing")
    assert [f["rule"] for f in state["findings"]] == [
        "PICTURE_OUTDATED",
        "APPROVAL_OUTDATED",
        "REVIEW_PAGE_OUTDATED",
    ]
    assert state["done"] == []
