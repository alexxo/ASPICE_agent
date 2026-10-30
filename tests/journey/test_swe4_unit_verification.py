"""Journey — stages 5 and 6 end to end: unit tests first, then the units.

Decision 3: the scenario runs on a small Python product, not the Java example,
so the gates run real product commands with this interpreter's pytest and ruff.
The product starts where stage 4 ends: checkpoints 1 to 3 approved and the
detailed design passing, on a feature branch off main. The loop of
agent/run_aspice_agent.md is driven with the agent's own tools; each attempt
writes the plugin's scripted output with the test builder and commits it, as
the plugin would.

- the tester's and the coder's methods are loaded with their rulebooks;
- red tests and stubs move the product to stage 6, code that passes them to stage 7.

Each rule a step could break is its gate's unit tests' to prove, and the
resolver's routing the routing tests' (Appendix A.5, *Fast by design*).
"""

import pytest
from product_builder import (
    approve_checkpoint,
    build_python_product,
    commit_all,
    install_plugins,
    record_stages_done,
    write_all_code,
    write_all_tests_and_stubs,
)

from agent.count_retries_tool import decide, record_attempt
from agent.load_skills_tool import load_skills
from agent.read_stages_tool import stage
from agent.record_stage_done_tool import record_stage_done
from agent.resolve_stage_tool import resolve_stage
from agent.run_gates_tool import reached_gates, run_gates

DESIGNED = ["diagram", "requirements", "architecture", "detailed_design"]


@pytest.fixture(autouse=True)
def _no_ci_base(monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)


@pytest.fixture
def product(tmp_path):
    """Where stage 4 ends: checkpoints 1–3 approved, the design passing."""
    root = build_python_product(tmp_path / "product")
    install_plugins(root)
    for checkpoint in (1, 2, 3):
        approve_checkpoint(root, checkpoint)
    record_stages_done(root, "architecture", "detailed_design")
    commit_all(root, "docs(approvals): stages 3 and 4 done REQ-0047")
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == ("unit_tests", "in_progress")
    assert {f["rule"] for f in state["reported"]} == {"MISSING_STUB", "MISSING_UNIT_TEST"}
    assert state["done"] == DESIGNED
    return root


def _attempts(root, stage_id, writers):
    """The plugin writes and commits, the stage's gates judge, the counter decides."""
    for write in writers:
        write(root)
        commit_all(root, f"feat: {stage_id} attempt REQ-0047")
        results = run_gates(root, reached_gates(root, stage(stage_id)))
        record_attempt(root, stage_id, results)
        decision = decide(root, stage_id)
        if decision["decision"] != "retry":
            break
    return decision


# ── what the plugins write ──────────────────────────────────────────────────


def red_tests_and_stubs(root):
    write_all_tests_and_stubs(root)


def the_units(root):
    write_all_code(root)


def nothing(root):
    """A retry that changes nothing — the plugin did not find the fault."""


# ── the scenarios ───────────────────────────────────────────────────────────


def test_the_tester_and_the_coder_are_loaded_with_their_rulebooks(product):
    tester = load_skills(product, "unit_tests")
    assert tester["plugin"]["skill_file"].endswith("plugins/swe/derive_unit_tests_plugin/SKILL.md")
    assert [p.split("/")[-2] for p in tester["framework_skills"]] == [
        "enforce_test_first_skill",
        "validate_env_config_skill",
        "create_security_tests_skill",
    ]
    coder = load_skills(product, "unit_construction")
    assert coder["plugin"]["skill_file"].endswith("plugins/swe/derive_unit_code_plugin/SKILL.md")
    assert [p.split("/")[-2] for p in coder["framework_skills"]] == [
        "enforce_test_first_skill",
        "construct_units_skill",
        "run_verification_suites_skill",
        "validate_env_config_skill",
        "create_security_tests_skill",
        "emit_log_events_skill",
    ]


def test_tests_first_then_the_units_move_the_product_to_stage_7(product):
    decision = _attempts(product, "unit_tests", [red_tests_and_stubs])
    assert decision["decision"] == "pass"
    record_stage_done(product, "unit_tests")
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("unit_construction", "in_progress")
    assert {f["rule"] for f in state["reported"]} == {
        "FAILED_TEST",
        "MISSING_SECURITY_TEST",
        "UNTESTED_UNIT",
        "UNTESTED_VARIABLE",
        "UNUSED_VARIABLE",
    }
    assert state["done"] == [*DESIGNED, "unit_tests"]

    decision = _attempts(product, "unit_construction", [the_units])
    assert decision["decision"] == "pass"
    record_stage_done(product, "unit_construction")
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("integration_verification", "in_progress")
    assert state["done"] == [*DESIGNED, "unit_tests", "unit_construction"]
