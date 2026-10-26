"""Journey — the SWE.1 stage end to end, on a copy of the example product.

The loop of agent/run_aspice_agent.md is driven step by step with the agent's
own tools. The only thing replaced is the LLM doing the work: each attempt
copies a scripted plugin output (tests/journey/plugin_outputs/) into the
product, as the plugin would write it. Two outcomes:

- a plugin produces requirements that pass the gates, and checkpoint 2 moves
  the product on;
- a stuck requirement is retried, and reaches the architect after the first
  run and 3 retries.

Each rule a step could break is its gate's unit tests' to prove, and the
resolver's routing the routing tests' (Appendix A.5, *Fast by design*).
"""

import shutil
from datetime import datetime, timezone

from product_builder import render_reviews

from agent.count_retries_tool import decide, record_attempt
from agent.load_skills_tool import load_skills
from agent.read_config_tool import read_config
from agent.read_stages_tool import stage
from agent.record_checkpoint_tool import record_checkpoint
from agent.resolve_stage_tool import resolve_stage
from agent.run_gates_tool import run_gates

OUTPUTS = "tests/journey/plugin_outputs/requirements"


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
        render_reviews(product)
        results = run_gates(product, stage("requirements").gates)
        record_attempt(product, "requirements", results)
        decision = decide(product, "requirements")
        if decision["decision"] != "retry":
            break
    return decision


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


def test_a_stuck_requirement_reaches_the_architect(repo_root, product):
    _start(product)
    decision = _attempts(repo_root, product, ["stuck"] * 5)
    assert (decision["decision"], decision["attempts"]) == ("escalate", 4)
    report = (product / decision["escalation_report"]).read_text()
    assert report.count("UNKNOWN_ELEMENT") == 4
    assert report.count("## Attempt") == 4
    assert resolve_stage(product)["status"] == "in_progress"
