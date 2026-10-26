"""Journey — the SWE.2 architecture stage end to end, on a copy of the example product.

The product starts where the SWE.1 scenario ends: requirements derived and
approved at checkpoint 2. The loop of agent/run_aspice_agent.md is driven with
the agent's own tools; each attempt copies a scripted plugin output
(tests/journey/plugin_outputs/architecture/) into the product. The stage has
its checkpoint inside it: the stack is written and approved at checkpoint 3
before any component is designed.

- the stack is approved, the design passes the gates, and the product moves on.
- a diagram corrected after the design is approved again at checkpoint 1, the
  requirements again at checkpoint 2, and the product resumes where it was
  (§ 5 stages 1 and 2, rule 25; FB-39).

Each rule a step could break is its gate's unit tests' to prove, and the
resolver's routing the routing tests' (Appendix A.5, *Fast by design*).
"""

import shutil
from datetime import datetime, timezone

from product_builder import commit_all, render_reviews, write_picture

from agent.count_retries_tool import decide, record_attempt
from agent.load_skills_tool import load_skills
from agent.read_stages_tool import stage
from agent.record_checkpoint_tool import record_checkpoint
from agent.record_stage_done_tool import record_stage_done
from agent.resolve_stage_tool import resolve_stage
from agent.run_gates_tool import reached_gates, run_gates

OUTPUTS = "tests/journey/plugin_outputs"
APPROVED = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


def _write(repo_root, product, output):
    """The plugin writes its files where the product keeps them."""
    shutil.copytree(repo_root / OUTPUTS / output, product, dirs_exist_ok=True)


def _requirements_approved(repo_root, product):
    """Where the SWE.1 scenario ends: requirements derived and approved."""
    target = product / "docs" / "requirements" / "login.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(repo_root / OUTPUTS / "requirements" / "correct" / "login.md", target)
    render_reviews(product)
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


def test_a_corrected_diagram_is_approved_again_and_the_product_resumes(repo_root, product):
    _stack_approved(repo_root, product)
    assert _attempts(repo_root, product, ["correct"])["decision"] == "pass"
    commit_all(product, "architecture designed")
    record_stage_done(product, "architecture")

    spec = product / "docs/diagrams/login.sequence.json"
    spec.write_text(spec.read_text().replace("session opened", "session started"))
    write_picture(spec)
    commit_all(product, "the architect corrects the diagram")
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("diagram", "gates_failing")
    assert [f["rule"] for f in state["findings"]] == ["APPROVAL_OUTDATED"]

    record_checkpoint(product, 1, "approved", "Example Architect", "architect")
    render_reviews(product)
    commit_all(product, "diagrams approved again at checkpoint 1")
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("requirements", "gates_failing")
    assert [f["rule"] for f in state["findings"]] == ["APPROVAL_OUTDATED"]  # not APPROVED_TOO_LATE

    record_checkpoint(product, 2, "approved", "Example Architect", "architect")
    commit_all(product, "requirements approved again at checkpoint 2")
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("detailed_design", "in_progress")
    assert state["done"] == ["diagram", "requirements", "architecture"]
