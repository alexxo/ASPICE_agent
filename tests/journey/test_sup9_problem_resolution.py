"""Journey — stage 12 end to end: a crack recorded, reproduced first, repaired, confirmed.

The product starts where the flow ends: every stage done, delivered in a
reviewed pull request. The host is a recorded one (QF_HOST_FILE) and holds the
issues. Stage 12 runs on a defect, not in the flow; its gates run on every pull
request once the flow is done (decision 4 of the problem resolution stage).

- the agent loads the tester and the coder, with the repair rulebook;
- an analysed problem, its crack bench in a test-only commit, passes.

Each rule a step could break is its gate's unit tests' to prove, and the
resolver's routing the routing tests' (Appendix A.5, *Fast by design*).
"""

import json
import shutil
from datetime import datetime, timezone

import pytest
from product_builder import (
    AGENT,
    build_python_product,
    commit_all,
    install_plugins,
    issue,
    open_delivery,
    prepare_delivery,
    problem,
    record_stages_done,
    write_all_code,
    write_all_integration_tests,
    write_all_scenarios,
    write_all_software_tests,
    write_all_tests_and_stubs,
    write_events_code,
)

from agent.load_skills_tool import load_skills
from agent.record_checkpoint_tool import record_checkpoint
from agent.resolve_stage_tool import resolve_stage
from tools.read_product_config_tool import read_product_config
from tools.write_verification_report_tool import write_report

APPROVED = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
STAGE = "problem_resolution"
UNIT = "src/auth_service/count_failures.py"  # the unit the crack is in
BENCH = "src/auth_service/test_count_failures_lockout.py"
SOUND = "return value + 1"
CRACKED = "return value + (1 if value < 5 else 2)"  # from 5 failures on, each counts twice


@pytest.fixture(autouse=True)
def _no_ci_base(monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)


DONE_BY_THE_AGENT = (
    "architecture",
    "detailed_design",
    "unit_tests",
    "unit_construction",
    "integration_verification",
    "software_verification",
    "quality_assurance",
    "configuration_management",
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Where the flow ends, every wish with its scenario; copied for each test."""
    work = tmp_path_factory.mktemp("built")
    root = build_python_product(work / "product", branch="bugfix/REQ-0047-lockout")
    install_plugins(root)
    for checkpoint in (1, 2, 3):
        record_checkpoint(
            root, checkpoint, "approved", "Example Architect", "architect", now=APPROVED
        )
    commit_all(root, "docs(approvals): checkpoints 1 to 3 REQ-0047")
    for write, message in (
        (write_all_tests_and_stubs, "test(auth): every unit REQ-0047"),
        (write_all_code, "feat(auth): every unit REQ-0047"),
        (write_all_integration_tests, "test(auth): every component and flow REQ-0047"),
        (write_events_code, "feat(auth): the sign-in events REQ-0047"),
        (write_all_software_tests, "test(auth): every requirement REQ-0047"),
        (write_all_scenarios, "test(validation): a scenario for every wish REQ-0047"),
    ):
        write(root)
        commit_all(root, message)
    record_stages_done(root, *DONE_BY_THE_AGENT)
    commit_all(root, "docs(approvals): stages 3 to 10 done REQ-0047")
    prepare_delivery(root, work, ref="#1")
    unit = root / UNIT
    unit.write_text(unit.read_text().replace(SOUND, CRACKED))
    commit_all(root, "perf(auth): count failures faster REQ-0047")
    return root


@pytest.fixture
def product(built, tmp_path):
    root = tmp_path / "product"
    shutil.copytree(built, root, symlinks=True)
    return root


def _repair(root, number=12):
    """The tester's crack bench, failing in its test-only commit; then the coder's fix."""
    (root / BENCH).write_text(
        f"# @unit[count-failures] @problem[{number}]\nfrom count_failures import run\n\n\n"
        "def test_the_fifth_failure_counts_once():\n    assert run(5) == 6\n"
    )
    commit_all(root, f"test(auth): reproduce the lockout crack #{number}")
    unit = root / UNIT
    unit.write_text(unit.read_text().replace(CRACKED, SOUND))
    commit_all(root, f"fix(auth): count every failure once #{number}")


def _deliver(root, tmp_path, monkeypatch, *issues):
    """Write the report, and show the host the reviewed pull request and the issues."""
    write_report(read_product_config(root))
    host = open_delivery(root, tmp_path, reviewers=(AGENT,))
    data = json.loads(host.read_text())
    data["repositories"]["acme/login"]["issues"] = list(issues)
    host.write_text(json.dumps(data))
    monkeypatch.setenv("QF_HOST_FILE", str(host))


def _state(root):
    state = resolve_stage(root)
    return state["stage"], state["status"], sorted({f["rule"] for f in state["findings"]})


def test_the_repair_crew_is_the_tester_then_the_coder(product):
    loaded = load_skills(product, STAGE)
    assert loaded["plugin"]["skill_file"].endswith("derive_unit_tests_plugin/SKILL.md")
    assert [p["skill_file"].split("/")[-2] for p in loaded["also_plugins"]] == [
        "derive_unit_code_plugin"
    ]
    assert [p.split("/")[-2] for p in loaded["framework_skills"]] == [
        "resolve_problems_skill",
        "enforce_test_first_skill",
    ]


def test_an_analysed_crack_with_its_bench_passes(product, tmp_path, monkeypatch):
    _repair(product)
    _deliver(product, tmp_path, monkeypatch, issue(12, "problem", problem(12)))
    assert _state(product) == (None, "complete", [])
