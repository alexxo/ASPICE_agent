"""Journey — stage 9 end to end: the delivery desk.

The product starts where stage 8 ends, with what its first delivery needs: the
framework pinned as a released submodule, the CI file, the code owners and the
framework feedback log. The foreman opens the pull request; the reviewer agent
approves its head from its own account with the checklist; on a sampled pull
request a person approves too (decisions 1, 2 and 7 of the quality assurance
stage). The host is a recorded one (QF_HOST_FILE), as in the gates' tests.

- the reviewer is loaded with its rulebooks;
- the reviewer agent's approval moves the product through stages 10 and 11, every wish
  with its scenario, to the end of the flow.

Each rule a step could break is its gate's unit tests' to prove, and the
resolver's routing the routing tests' (Appendix A.5, *Fast by design*).
"""

from datetime import datetime, timezone

import pytest
from product_builder import (
    AGENT,
    build_python_product,
    commit_all,
    git_head,
    install_plugins,
    open_delivery,
    prepare_delivery,
    record_stages_done,
    write_all_code,
    write_all_integration_tests,
    write_all_scenarios,
    write_all_software_tests,
    write_all_tests_and_stubs,
    write_events_code,
    write_host,
)

from agent.load_skills_tool import load_skills
from agent.record_checkpoint_tool import record_checkpoint
from agent.record_stage_done_tool import record_stage_done
from agent.resolve_stage_tool import resolve_stage
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
    "software_verification",
]
STAGE = "quality_assurance"


@pytest.fixture(autouse=True)
def _no_ci_base(monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Where stage 8 ends, ready for its first delivery; copied for each test."""
    work = tmp_path_factory.mktemp("built")
    root = build_python_product(work / "product")
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
    record_stages_done(root, *BUILT[2:])
    commit_all(root, "docs(approvals): stages 3 to 8 done REQ-0047")
    prepare_delivery(root, work, ref="#1")
    return root


@pytest.fixture
def product(built, tmp_path, monkeypatch):
    import shutil

    root = tmp_path / "product"
    shutil.copytree(built, root, symlinks=True)
    write_report(read_product_config(root))
    framework = git_head(root / ".framework")
    host = write_host(tmp_path / "host.json", tags={"v6.0.0": framework})
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return root


def _deliver(root, tmp_path, monkeypatch, **pull):
    monkeypatch.setenv("QF_HOST_FILE", str(open_delivery(root, tmp_path, **pull)))


def _finish(root):
    """The agent records stages 9 and 10 done once their own gates pass, and
    commits each record; the commit is a new tree, so the report is written
    again first, as the agent does before every stage's gates from stage 8 on."""
    record_stage_done(root, STAGE)
    commit_all(root, "docs(approvals): stage 9 done REQ-0047")
    write_report(read_product_config(root))
    record_stage_done(root, "configuration_management")
    commit_all(root, "docs(approvals): stage 10 done REQ-0047")
    write_report(read_product_config(root))


def test_the_reviewer_is_loaded_with_its_rulebooks(product):
    loaded = load_skills(product, STAGE)
    assert loaded["plugin"]["skill_file"].endswith("plugins/sup/derive_review_plugin/SKILL.md")
    assert [p.split("/")[-2] for p in loaded["framework_skills"]] == [
        "review_code_skill",
        "report_framework_feedback_skill",
        "track_nonconformances_skill",
    ]


def test_the_reviewer_agents_approval_moves_the_product_on(product, tmp_path, monkeypatch):
    _deliver(product, tmp_path, monkeypatch, reviewers=(AGENT,))
    _finish(product)
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == (None, "complete")
    assert state["done"] == [*BUILT, STAGE, "configuration_management", "validation"]
