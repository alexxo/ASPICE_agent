"""Scenario — stages 5 and 6 end to end: unit tests first, then the units.

Decision 3: the scenario runs on a small Python product, not the Java example,
so the gates run real product commands with this interpreter's pytest and ruff.
The product starts where stage 4 ends: checkpoints 1 to 3 approved and the
detailed design passing, on a feature branch off main. The loop of
agent/run_aspice_agent.md is driven with the agent's own tools; each attempt
writes the plugin's scripted output with the test builder and commits it, as
the plugin would.

- the tester's and the coder's methods are loaded with their rulebooks;
- red tests and stubs move the product to stage 6, code that passes them to stage 7;
- a test that passes against its stub is caught, and fixed by a retry;
- code that stays wrong reaches the architect after the first run and 3 retries;
- a coder who changes a test together with the code is caught.
"""

import json
from datetime import datetime, timezone

import pytest
from product_builder import (
    build_python_product,
    commit_all,
    install_plugins,
    write_all_code,
    write_all_tests_and_stubs,
    write_code,
    write_unit_test,
)

from agent.count_retries_tool import decide, record_attempt
from agent.load_skills_tool import load_skills
from agent.read_stages_tool import stage
from agent.record_checkpoint_tool import record_checkpoint
from agent.resolve_stage_tool import resolve_stage
from agent.run_gates_tool import reached_gates, run_gates

APPROVED = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
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
        record_checkpoint(
            root, checkpoint, "approved", "Example Architect", "architect", now=APPROVED
        )
    commit_all(root, "checkpoints 1 to 3 approved")
    state = resolve_stage(root)
    assert (state["stage"], state["status"]) == ("unit_tests", "gates_failing")
    assert {f["rule"] for f in state["findings"]} == {"MISSING_STUB", "MISSING_UNIT_TEST"}
    assert state["done"] == DESIGNED
    return root


def _attempts(root, stage_id, writers):
    """The plugin writes and commits, the stage's gates judge, the counter decides."""
    for write in writers:
        write(root)
        commit_all(root, f"{stage_id}: attempt")
        results = run_gates(root, reached_gates(root, stage(stage_id)))
        record_attempt(root, stage_id, results)
        decision = decide(root, stage_id)
        if decision["decision"] != "retry":
            break
    return decision


def _rules(root, stage_id, number):
    log = root / ".qf/attempts" / stage_id / f"attempt-{number}.json"
    return sorted(f["rule"] for gate in json.loads(log.read_text()) for f in gate["findings"])


# ── what the plugins write ──────────────────────────────────────────────────


def red_tests_and_stubs(root):
    write_all_tests_and_stubs(root)


def one_test_green_on_its_stub(root):
    write_all_tests_and_stubs(root)
    write_unit_test(root, "auth-service", "count-failures", assertion="run(1) == 0")


def that_test_fixed(root):
    write_unit_test(root, "auth-service", "count-failures")


def the_units(root):
    write_all_code(root)


def one_unit_wrong(root):
    write_all_code(root)
    (root / "src" / "auth_service" / "count_failures.py").write_text(
        "# @unit[count-failures]\n\n\ndef run(value):\n    return value + 2\n"
    )


def the_units_and_a_loosened_test(root):
    write_all_code(root)
    write_unit_test(root, "auth-service", "open-session", assertion="run(1) is not None")


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
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("unit_construction", "gates_failing")
    assert {f["rule"] for f in state["findings"]} == {
        "FAILED_TEST",
        "MISSING_SECURITY_TEST",
        "UNTESTED_UNIT",
        "UNTESTED_VARIABLE",
        "UNUSED_VARIABLE",
    }
    assert state["done"] == [*DESIGNED, "unit_tests"]

    decision = _attempts(product, "unit_construction", [the_units])
    assert decision["decision"] == "pass"
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == ("integration_verification", "gates_failing")
    assert state["done"] == [*DESIGNED, "unit_tests", "unit_construction"]


def test_a_test_green_on_its_stub_is_caught_and_fixed_by_a_retry(product):
    decision = _attempts(product, "unit_tests", [one_test_green_on_its_stub, that_test_fixed])
    assert decision["decision"] == "pass"
    assert _rules(product, "unit_tests", 1) == ["TEST_NOT_FAILING"]
    assert _rules(product, "unit_tests", 2) == []


def test_code_that_stays_wrong_reaches_the_architect(product):
    _attempts(product, "unit_tests", [red_tests_and_stubs])
    decision = _attempts(product, "unit_construction", [one_unit_wrong, *[nothing] * 4])
    assert (decision["decision"], decision["attempts"]) == ("escalate", 4)
    assert _rules(product, "unit_construction", 4) == ["FAILED_TEST", "UNTESTED_UNIT"]


def test_a_coder_who_loosens_a_test_is_caught(product):
    _attempts(product, "unit_tests", [red_tests_and_stubs])
    decision = _attempts(product, "unit_construction", [the_units_and_a_loosened_test])
    assert decision["decision"] == "retry"
    assert _rules(product, "unit_construction", 1) == ["TEST_CHANGED_WITH_CODE"]


def test_requirement_markers_on_the_units_must_name_real_requirements(product):
    _attempts(product, "unit_tests", [red_tests_and_stubs])

    def with_a_wrong_marker(root):
        write_all_code(root)
        write_code(root, "auth-service", "count-failures", sdoc="REQ-9999")

    decision = _attempts(product, "unit_construction", [with_a_wrong_marker])
    assert decision["decision"] == "retry"
    assert _rules(product, "unit_construction", 1) == ["UNKNOWN_REQUIREMENT"]
