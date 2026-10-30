"""Journey — stage 8 end to end: the whole software against every requirement.

The product starts where stage 7 ends: its components and flows tested. The
bridge tester writes the plan's software section, the end-to-end and software
tests, the bench that measures the non-functional requirements and the
observability definition in a test-only commit; the coder then changes the
code until they pass (decision 1 of the software verification stage), and
the crew writes the verification report of the tree (decision 8). The loop of
agent/run_aspice_agent.md is driven with the agent's own tools, as in the
scenarios of stages 5 to 7.

- the bridge tester and the coder are loaded with their rulebooks;
- tests, measurements, definitions and the report move the product to stage 9.

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
    write_all_integration_tests,
    write_all_software_tests,
    write_all_tests_and_stubs,
    write_events_code,
)

from agent.count_retries_tool import decide, record_attempt
from agent.load_skills_tool import load_skills
from agent.read_stages_tool import stage
from agent.record_stage_done_tool import record_stage_done
from agent.resolve_stage_tool import resolve_stage
from agent.run_gates_tool import reached_gates, run_gates
from tools.read_product_config_tool import read_product_config
from tools.write_verification_report_tool import write_report

BUILT = [
    "diagram",
    "requirements",
    "architecture",
    "detailed_design",
    "unit_tests",
    "unit_construction",
    "integration_verification",
]
STAGE = "software_verification"


@pytest.fixture(autouse=True)
def _no_ci_base(monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)


@pytest.fixture
def product(tmp_path):
    """Where stage 7 ends: every component and flow tested, the events emitted."""
    root = build_python_product(tmp_path / "product")
    install_plugins(root)
    for checkpoint in (1, 2, 3):
        approve_checkpoint(root, checkpoint)
    write_all_tests_and_stubs(root)
    commit_all(root, "test(auth): every unit REQ-0047")
    write_all_code(root)
    commit_all(root, "feat(auth): every unit REQ-0047")
    write_all_integration_tests(root)
    commit_all(root, "test(auth): every component and flow REQ-0047")
    write_events_code(root)
    commit_all(root, "feat(auth): the sign-in events REQ-0047")
    record_stages_done(root, *BUILT[2:])
    commit_all(root, "docs(approvals): stages 3 to 7 done REQ-0047")
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == (STAGE, "in_progress")
    assert {f["rule"] for f in state["reported"]} == {
        "UNVERIFIED_REQUIREMENT",
        "MISSING_MEASUREMENT",
        "UNOBSERVED_REQUIREMENT",
        "MISSING_REPORT",
    }
    assert state["done"] == BUILT
    return root


def _attempts(root, writers, report=True):
    """Each attempt: the bridge tester's and the coder's work, the report of the
    tree, then the stage's gates."""
    for write in writers:
        write(root)
        commit_all(root, f"feat: {STAGE} attempt REQ-0047")
        if report:
            write_report(read_product_config(root))
        results = run_gates(root, reached_gates(root, stage(STAGE)))
        record_attempt(root, STAGE, results)
        decision = decide(root, STAGE)
        if decision["decision"] != "retry":
            break
    return decision


# ── what the plugins write ──────────────────────────────────────────────────


def the_bridge_tester(root):
    write_all_software_tests(root)


# ── the scenarios ───────────────────────────────────────────────────────────


def test_the_bridge_tester_and_the_coder_are_loaded_with_their_rulebooks(product):
    loaded = load_skills(product, STAGE)
    assert loaded["plugin"]["skill_file"].endswith(
        "plugins/swe/derive_software_tests_plugin/SKILL.md"
    )
    (coder,) = loaded["also_plugins"]
    assert coder["skill_file"].endswith("plugins/swe/derive_unit_code_plugin/SKILL.md")
    assert [p.split("/")[-2] for p in loaded["framework_skills"]] == [
        "verify_software_skill",
        "configure_observability_skill",
        "specify_nfr_measurement_skill",
    ]


def test_tests_measurements_and_the_report_move_the_product_to_stage_9(product):
    decision = _attempts(product, [the_bridge_tester])
    assert decision["decision"] == "pass"
    commit_all(product, "test(auth): software verified REQ-0047")
    write_report(read_product_config(product))  # the commit is a new tree
    record_stage_done(product, STAGE)
    commit_all(product, "docs(approvals): stage 8 done REQ-0047")
    write_report(read_product_config(product))  # and so is the record's commit
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("quality_assurance", "in_progress")
    assert state["done"] == [*BUILT, STAGE]
