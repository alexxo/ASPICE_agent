"""Journey — the SWE.3 detailed design stage end to end, on a copy of the example product.

The product starts where the SWE.2 scenario ends: requirements approved at
checkpoint 2, the stack approved at checkpoint 3, and an architecture that
passes its gates. The loop of agent/run_aspice_agent.md is driven with the
agent's own tools; each attempt copies a scripted plugin output
(tests/journey/plugin_outputs/detailed_design/) into the product. Stage 4 has
no checkpoint: the design is agreed at the pull request.

- the method and the diagram plugin are both loaded;
- a design that passes the gate moves the product to stage 5;
- after a change request it is recorded again, naming the changed requirements,
  with no decision record of its own for each (FB-64).

Each rule a step could break is its gate's unit tests' to prove, and the
resolver's routing the routing tests' (Appendix A.5, *Fast by design*).
"""

import shutil

import yaml
from product_builder import approve_checkpoint, commit_all, render_reviews

from agent.count_retries_tool import decide, record_attempt
from agent.load_skills_tool import load_skills
from agent.read_stages_tool import stage
from agent.record_stage_done_tool import record_stage_done
from agent.resolve_stage_tool import resolve_stage
from agent.run_gates_tool import reached_gates, run_gates

OUTPUTS = "tests/journey/plugin_outputs"


def _write(repo_root, product, output):
    """The plugin writes its files where the product keeps them."""
    shutil.copytree(repo_root / OUTPUTS / output, product, dirs_exist_ok=True)


def _architecture_done(repo_root, product):
    """Where the SWE.2 scenario ends: stack approved, architecture passing."""
    target = product / "docs" / "requirements" / "login.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(repo_root / OUTPUTS / "requirements" / "correct" / "login.md", target)
    render_reviews(product)
    approve_checkpoint(product, 2)
    _write(repo_root, product, "architecture/stack")
    commit_all(product, "stack written")
    approve_checkpoint(product, 3)
    _write(repo_root, product, "architecture/correct")
    commit_all(product, "architecture written")
    record_stage_done(product, "architecture")
    commit_all(product, "architecture recorded as done")
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("detailed_design", "in_progress")
    assert [f["rule"] for f in state["reported"]] == ["NO_DETAILED_DESIGN"]
    assert state["done"] == ["diagram", "requirements", "architecture"]


def _attempts(product_root, repo_root, outputs):
    """The plugin writes, the stage's gate judges, the counter decides."""
    detailed_design = stage("detailed_design")
    for output in outputs:
        _write(repo_root, product_root, f"detailed_design/{output}")
        results = run_gates(product_root, reached_gates(product_root, detailed_design))
        record_attempt(product_root, "detailed_design", results)
        decision = decide(product_root, "detailed_design")
        if decision["decision"] != "retry":
            break
    return decision


def test_the_method_and_the_diagram_plugin_are_loaded(repo_root, product):
    _architecture_done(repo_root, product)
    loaded = load_skills(product, "detailed_design")
    assert loaded["plugin"]["skill_file"].endswith(
        "plugins/swe/derive_detailed_design_plugin/SKILL.md"
    )
    assert [p["name"] for p in loaded["also_plugins"]] == ["archify"]
    assert [p.split("/")[-2] for p in loaded["framework_skills"]] == [
        "write_detailed_design_skill",
        "validate_env_config_skill",
        "record_decisions_skill",
    ]


def test_a_passing_design_moves_the_product_to_stage_5(repo_root, product):
    _architecture_done(repo_root, product)
    decision = _attempts(product, repo_root, ["correct"])
    assert decision["decision"] == "pass"
    commit_all(product, "detailed design written")
    record_stage_done(product, "detailed_design")
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("unit_tests", "in_progress")
    rules = {f["rule"] for f in state["reported"]}
    # stage 5 is due: its plan first, whose unit suite says which files are the tests
    assert "MISSING_VERIFICATION_PLAN" in rules
    assert "MISSING_UNIT_TEST" not in rules
    assert state["done"] == ["diagram", "requirements", "architecture", "detailed_design"]


def test_a_changed_requirement_needs_no_decision_record_of_its_own(repo_root, product, monkeypatch):
    """A record only for a real choice (FB-64): the stage is recorded with the change named."""
    import agent.record_stage_done_tool as tool

    _architecture_done(repo_root, product)
    _attempts(product, repo_root, ["correct"])
    commit_all(product, "detailed design brought up to the change")
    monkeypatch.setattr(tool, "requirements_changed", lambda *_: ["REQ-0001"])
    path = record_stage_done(product, "detailed_design")
    assert yaml.safe_load(path.read_text())["requirements_changed"] == ["REQ-0001"]
