"""Journey — stage 7 end to end: the components alone, then joined along the flows.

The product starts where stage 6 ends: its units built tests first. The
assembler writes the plan's integration section, the component tests and the
flow's integration test in a test-only commit; the coder then changes the code
until they pass (decision 1 of the integration stage), and commits. The loop of
agent/run_aspice_agent.md is driven with the agent's own tools, as in the
scenario of stages 5 and 6.

- the assembler and the coder are loaded with their rulebooks;
- tests, then the code that emits the log events, move the product to stage 8.

Each rule a step could break is its gate's unit tests' to prove, and the
resolver's routing the routing tests' (Appendix A.5, *Fast by design*).
"""

from datetime import datetime, timezone

import pytest
from product_builder import (
    build_python_product,
    commit_all,
    install_plugins,
    record_stages_done,
    write_all_code,
    write_all_integration_tests,
    write_all_tests_and_stubs,
    write_events_code,
)

from agent.count_retries_tool import decide, record_attempt
from agent.load_skills_tool import load_skills
from agent.read_stages_tool import stage
from agent.record_checkpoint_tool import record_checkpoint
from agent.record_stage_done_tool import record_stage_done
from agent.resolve_stage_tool import resolve_stage
from agent.run_gates_tool import reached_gates, run_gates

APPROVED = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
BUILT = ["diagram", "requirements", "architecture", "detailed_design", "unit_tests"]
STAGE = "integration_verification"


@pytest.fixture(autouse=True)
def _no_ci_base(monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)


@pytest.fixture
def product(tmp_path):
    """Where stage 6 ends: every unit built, tests first."""
    root = build_python_product(tmp_path / "product")
    install_plugins(root)
    for checkpoint in (1, 2, 3):
        record_checkpoint(
            root, checkpoint, "approved", "Example Architect", "architect", now=APPROVED
        )
    commit_all(root, "docs(approvals): checkpoints 1 to 3 REQ-0047")
    write_all_tests_and_stubs(root)
    commit_all(root, "test(auth): every unit REQ-0047")
    write_all_code(root)
    commit_all(root, "feat(auth): every unit REQ-0047")
    record_stages_done(root, "architecture", "detailed_design", "unit_tests", "unit_construction")
    commit_all(root, "docs(approvals): stages 3 to 6 done REQ-0047")
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == (STAGE, "in_progress")
    assert {f["rule"] for f in state["reported"]} == {
        "MISSING_COMPONENT_TEST",
        "MISSING_FLOW_TEST",
        "UNTESTED_EVENT",
        "UNTESTED_INTERFACE",
    }
    assert state["done"] == [*BUILT, "unit_construction"]
    return root


def _attempts(root, writers):
    """Each attempt: the assembler's and the coder's work, then the stage's gates."""
    for write in writers:
        write(root)
        commit_all(root, f"feat: {STAGE} attempt REQ-0047")
        results = run_gates(root, reached_gates(root, stage(STAGE)))
        record_attempt(root, STAGE, results)
        decision = decide(root, STAGE)
        if decision["decision"] != "retry":
            break
    return decision


# ── what the plugins write ──────────────────────────────────────────────────


def the_assembler_then_the_coder(root):
    write_all_integration_tests(root)
    commit_all(root, "test(auth): every component and flow REQ-0047")
    write_events_code(root)


# ── the scenarios ───────────────────────────────────────────────────────────


def test_the_assembler_and_the_coder_are_loaded_with_their_rulebooks(product):
    loaded = load_skills(product, STAGE)
    assert loaded["plugin"]["skill_file"].endswith(
        "plugins/swe/derive_integration_tests_plugin/SKILL.md"
    )
    (coder,) = loaded["also_plugins"]
    assert coder["skill_file"].endswith("plugins/swe/derive_unit_code_plugin/SKILL.md")
    assert [p.split("/")[-2] for p in loaded["framework_skills"]] == [
        "verify_integration_skill",
        "emit_log_events_skill",
    ]


def test_tests_then_the_events_move_the_product_to_stage_8(product):
    decision = _attempts(product, [the_assembler_then_the_coder])
    assert decision["decision"] == "pass"
    record_stage_done(product, STAGE)
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("software_verification", "in_progress")
    assert state["done"] == [*BUILT, "unit_construction", STAGE]
