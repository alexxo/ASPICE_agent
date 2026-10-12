"""Scenario — stage 13 end to end: a change ordered, signed, then built.

The product starts where the flow ends: every stage done, delivered in a
reviewed pull request. The host is a recorded one (QF_HOST_FILE) and holds the
issues. Stage 13 runs when the customer changes their mind, not in the flow; its
gates run on every pull request once the flow is done (decision 4 of the change
request stage).

- the agent loads the change desk's rulebook and no plugin;
- a commit building a change nobody signed holds the pull request at stage 13;
- the same change, signed by an approver before the commit, passes;
- a change that names an item the product does not have is caught.
"""

import json
import shutil
from datetime import datetime, timezone

import pytest
from product_builder import (
    AGENT,
    BEFORE,
    PERSON,
    build_python_product,
    change,
    comment,
    commit_all,
    install_plugins,
    issue,
    open_delivery,
    prepare_delivery,
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
STAGE = "change_request"
CR = "change-request"


@pytest.fixture(autouse=True)
def _no_ci_base(monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Where the flow ends, every wish with its scenario; copied for each test."""
    work = tmp_path_factory.mktemp("built")
    root = build_python_product(work / "product", branch="feature/REQ-0047-lock-later")
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
    prepare_delivery(root, work, ref="#1")
    return root


@pytest.fixture
def product(built, tmp_path):
    root = tmp_path / "product"
    shutil.copytree(built, root, symlinks=True)
    (root / "docs/lockout-notes.md").write_text("Ten failed sign-ins lock an account.\n")
    commit_all(root, "docs(auth): note the new lockout limit #20")  # builds change #20
    return root


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


def test_the_change_desk_has_a_rulebook_and_no_plugin(product):
    loaded = load_skills(product, STAGE)
    assert loaded["plugin"] is None
    assert [p.split("/")[-2] for p in loaded["framework_skills"]] == ["manage_changes_skill"]


def test_a_change_nobody_signed_holds_its_pull_request(product, tmp_path, monkeypatch):
    _deliver(product, tmp_path, monkeypatch, issue(20, CR, change(20)))
    assert _state(product) == (STAGE, "gates_failing", ["UNAPPROVED_CHANGE"])


def test_a_change_signed_before_it_was_built_passes(product, tmp_path, monkeypatch):
    signed = comment(PERSON, "/approve-change", BEFORE)
    _deliver(product, tmp_path, monkeypatch, issue(20, CR, change(20), comments=[signed]))
    assert _state(product) == (None, "complete", [])


def test_a_change_naming_an_unknown_requirement_is_caught(product, tmp_path, monkeypatch):
    signed = comment(PERSON, "/approve-change", BEFORE)
    affected = {"wishes": ["W-02"], "elements": [], "requirements": ["REQ-9999"]}
    order = issue(20, CR, change(20, affected=affected), comments=[signed])
    _deliver(product, tmp_path, monkeypatch, order)
    assert _state(product) == (STAGE, "gates_failing", ["UNKNOWN_AFFECTED_ITEM"])
