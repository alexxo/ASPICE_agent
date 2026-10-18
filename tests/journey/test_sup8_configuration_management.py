"""Journey — stage 10 end to end: the librarian and the official baseline.

The product starts where stage 9 ends, every commit of its feature branch a
Conventional Commit naming its requirement.
The host is a recorded one (QF_HOST_FILE), as in the gates' tests (decisions 1–5
of the configuration management stage).

- the agent loads the librarian's rulebook and no plugin;
- a delivery by convention, every wish with its scenario, passes stages 10 and 11;
- a release is a pull request: the tool writes its record, the gates accept it;
- after the merge the release workflow tags it, and the baseline is checked.

Each rule a step could break is its gate's unit tests' to prove, and the
resolver's routing the routing tests' (Appendix A.5, *Fast by design*).
"""

import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from product_builder import (
    AGENT,
    build_python_product,
    commit_all,
    git_head,
    install_plugins,
    open_delivery,
    prepare_delivery,
    pull_request,
    record_stages_done,
    review,
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
from agent.resolve_stage_tool import resolve_stage
from gates.sup import verify_baseline_gate
from tools.read_product_config_tool import read_product_config
from tools.write_release_tool import main as write_release
from tools.write_verification_report_tool import write_report

APPROVED = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
STAGE = "configuration_management"
FEATURE = "feature/REQ-0047-lockout"
RELEASE = "templates/github/release.yml"
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _no_ci_base(monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)


def git(root, *args):
    who = ["-c", "user.name=test", "-c", "user.email=test@example.org"]
    return subprocess.run(
        ["git", "-C", str(root), *who, *args], check=True, capture_output=True, text=True
    ).stdout


DONE_BY_THE_AGENT = (
    "architecture",
    "detailed_design",
    "unit_tests",
    "unit_construction",
    "integration_verification",
    "software_verification",
    "quality_assurance",
    STAGE,
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Where stage 9 begins, every commit by convention; copied for each test."""
    work = tmp_path_factory.mktemp("built")
    root = build_python_product(work / "product", branch=FEATURE)
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
    return root


@pytest.fixture
def product(built, tmp_path, monkeypatch):
    root = tmp_path / "product"
    shutil.copytree(built, root, symlinks=True)
    write_report(read_product_config(root))
    monkeypatch.setenv("QF_HOST_FILE", str(open_delivery(root, tmp_path, reviewers=(AGENT,))))
    return root


def _state(root):
    state = resolve_stage(root)
    return state["stage"], state["status"], sorted({f["rule"] for f in state["findings"]})


def _merge(root, branch, number):
    git(root, "checkout", "-q", "main")
    git(root, "merge", "-q", "--no-ff", "-m", f"Merge pull request #{number}", branch)
    return git_head(root)


def _propose(root, tmp_path, monkeypatch, merged, message):
    """Commit to the release branch; the host shows its pull request reviewed at
    the new head, and the feature's pull request merged."""
    commit_all(root, message)
    write_report(read_product_config(root))
    head = git_head(root)
    delivery = pull_request(
        1, merged, branch=FEATURE, merged=True, commits=[merged], reviews=[review(AGENT, merged)]
    )
    release = pull_request(
        2,
        head,
        branch="release/v1.0.0",
        files=["releases/1.0.0.yaml"],
        reviews=[review(AGENT, head)],
    )
    tags = {"v6.0.0": git_head(root / ".framework")}
    host = write_host(tmp_path / "release.json", pulls=[delivery, release], tags=tags)
    monkeypatch.setenv("QF_HOST_FILE", str(host))


def _tag_script(root):
    """The release workflow's tag step, run against this framework and a local origin."""
    steps = yaml.safe_load((REPO_ROOT / RELEASE).read_text())["jobs"]["release"]["steps"]
    (step,) = (s for s in steps if s.get("name") == "Tag the accepted release")
    script = step["run"].replace("python .framework/", f"{sys.executable} {REPO_ROOT}/")
    return subprocess.run(["bash", "-c", script], cwd=root, capture_output=True, text=True)


def test_the_librarian_has_a_rulebook_and_no_plugin(product):
    loaded = load_skills(product, STAGE)
    assert loaded["plugin"] is None
    assert [p.split("/")[-2] for p in loaded["framework_skills"]] == ["record_baseline_skill"]


def test_a_delivery_by_convention_passes_stages_10_and_11(product):
    state = resolve_stage(product)
    assert (state["stage"], state["status"]) == (None, "complete")
    assert state["done"][-3:] == ["quality_assurance", STAGE, "validation"]


def test_a_release_is_proposed_and_tagged_after_its_merge(product, tmp_path, monkeypatch):
    merged = _merge(product, FEATURE, 1)

    # The release pull request: the tool writes the record, nobody chooses the number.
    git(product, "checkout", "-q", "-b", "release/v1.0.0")
    assert write_release(["--root", str(product)]) == 0
    record = product / "releases/1.0.0.yaml"
    written = record.read_text()
    assert yaml.safe_load(written)["version"] == "1.0.0"
    record.write_text(written.replace("- src\n", ""))  # an item left out by hand
    _propose(product, tmp_path, monkeypatch, merged, "chore(release): 1.0.0 #2")
    assert _state(product) == (STAGE, "gates_failing", ["INCOMPLETE_RELEASE_RECORD"])
    record.write_text(written)
    _propose(product, tmp_path, monkeypatch, merged, "fix(release): list every change #2")
    assert resolve_stage(product)["stage"] == "validation"

    # After the merge, the release workflow stamps the baseline.
    _merge(product, "release/v1.0.0", 2)
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    git(product, "remote", "set-url", "--push", "origin", str(origin))
    tagged = _tag_script(product)
    assert tagged.returncode == 0, tagged.stderr
    assert git(product, "cat-file", "-t", "v1.0.0").strip() == "tag"
    assert git(product, "rev-parse", "v1.0.0^{commit}").strip() == git_head(product)
    config = read_product_config(product)
    assert verify_baseline_gate.check(config) == []

    # A merge without a new record tags nothing.
    again = _tag_script(product)
    assert (again.returncode, again.stdout.strip()) == (0, "No release in this merge.")
    assert git(product, "tag", "--list").split() == ["v1.0.0"]
