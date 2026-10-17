"""Scenario — stage 8 end to end: the whole software against every requirement.

The product starts where stage 7 ends: its components and flows tested. The
bridge tester writes the plan's software section, the end-to-end and software
tests, the bench that measures the non-functional requirements and the
observability definition in a test-only commit; the coder then changes the
code until they pass (decision 1 of the software verification stage), and
the crew writes the verification report of the tree (decision 8). The loop of
agent/run_aspice_agent.md is driven with the agent's own tools, as in the
scenarios of stages 5 to 7.

- the bridge tester and the coder are loaded with their rulebooks;
- tests, measurements, definitions and the report move the product to stage 9;
- a measured value beyond its threshold is caught;
- a coder who loosens an end-to-end test is caught;
- tests without the plan's software section are caught;
- a report written before the last commit is missing for the new tree.
"""

import json
from datetime import datetime, timezone

import pytest
from product_builder import (
    build_python_product,
    commit_all,
    install_plugins,
    record_stages_done,
    write_all_code,
    write_all_integration_tests,
    write_all_software_tests,
    write_all_tests_and_stubs,
    write_bench_test,
    write_e2e_test,
    write_events_code,
    write_observability,
    write_software_test,
)

from agent.count_retries_tool import decide, record_attempt
from agent.load_skills_tool import load_skills
from agent.read_stages_tool import stage
from agent.record_checkpoint_tool import record_checkpoint
from agent.record_stage_done_tool import record_stage_done
from agent.resolve_stage_tool import resolve_stage
from agent.run_gates_tool import reached_gates, run_gates
from tools.read_product_config_tool import read_product_config
from tools.write_verification_report_tool import write_report

APPROVED = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
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
        record_checkpoint(
            root, checkpoint, "approved", "Example Architect", "architect", now=APPROVED
        )
    commit_all(root, "docs(approvals): checkpoints 1 to 3 REQ-0047")
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


def _rules(root, number):
    log = root / ".qf/attempts" / STAGE / f"attempt-{number}.json"
    return sorted(f["rule"] for gate in json.loads(log.read_text()) for f in gate["findings"])


# ── what the plugins write ──────────────────────────────────────────────────


def the_bridge_tester(root):
    write_all_software_tests(root)


def the_bridge_tester_measuring_too_many(root):
    write_all_software_tests(root)
    write_bench_test(root, value="run(5)")  # 6 failed sign-ins, threshold <= 5


def the_bridge_tester_then_a_coder_loosening_a_test(root):
    write_all_software_tests(root)
    commit_all(root, "test(auth): every requirement REQ-0047")
    write_events_code(root)  # a code change, in the same commit as the loosened test
    (root / "src/auth_service/check_credentials.py").write_text(
        (root / "src/auth_service/check_credentials.py").read_text() + "\n# tidied\n"
    )
    write_e2e_test(root, assertion="run(1) is not None")


def tested_without_the_plan(root):
    write_e2e_test(root)
    write_software_test(root)
    write_bench_test(root)
    write_observability(root)


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


def test_a_measured_value_beyond_its_threshold_is_caught(product):
    decision = _attempts(product, [the_bridge_tester_measuring_too_many])
    assert decision["decision"] == "retry"
    assert _rules(product, 1) == ["THRESHOLD_NOT_MET"] * 3


def test_a_coder_who_loosens_an_end_to_end_test_is_caught(product):
    decision = _attempts(product, [the_bridge_tester_then_a_coder_loosening_a_test])
    assert decision["decision"] == "retry"
    assert _rules(product, 1) == ["TEST_CHANGED_WITH_CODE"]


def test_tests_without_the_plans_software_section_are_caught(product):
    decision = _attempts(product, [tested_without_the_plan])
    assert decision["decision"] == "retry"
    assert _rules(product, 1) == ["MISSING_SOFTWARE_SECTION"]


def test_without_the_report_of_the_tree_the_stage_does_not_pass(product):
    decision = _attempts(product, [the_bridge_tester], report=False)
    assert decision["decision"] == "retry"
    assert _rules(product, 1) == ["MISSING_REPORT"]
