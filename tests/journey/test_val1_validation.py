"""Journey — stage 11 end to end: the village crosses, and accepts the release.

The product starts where stage 10 ends: every wish has its scenario — two
automated, run by the validation suite, and a guided demo run by a person —
listed in the plan's validation section. The host is a recorded one
(QF_HOST_FILE), as in the gates' tests.

- the agent loads the village crew's method and the validation rulebook;
- a release is validated on its pull request from branch checkpoint/5: the
  tool records the deployed commit and the automated results, a person adds
  the demo's, and the merge waits for the architect's approval on behalf of the
  customer (seal 5), red in CI until it is given;
- after the merge, the merge is the acceptance and the GitHub Release says so;
  after the tag, the release keeps its validation record.

Each rule a step could break is its gate's unit tests' to prove, and the
resolver's routing the routing tests' (Appendix A.5, *Fast by design*).
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from product_builder import (
    AGENT,
    DEMO,
    PERSON,
    approve_checkpoint,
    build_python_product,
    checkpoint_pulls,
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
from agent.resolve_stage_tool import main as resolve_main
from agent.resolve_stage_tool import resolve_stage
from gates.val import verify_release_evidence_gate
from tools.read_approvals_tool import approval_state
from tools.read_product_config_tool import read_product_config
from tools.write_release_tool import main as write_release
from tools.write_release_tool import release_notes
from tools.write_validation_record_tool import main as write_validation_record
from tools.write_verification_report_tool import PAGE, write_report

STAGE = "validation"
FEATURE = "feature/REQ-0047-lockout"
RELEASE = "checkpoint/5"  # the release's pull request is checkpoint 5
RECORD = "validation/records/1.0.0.yaml"
WORKFLOW = "templates/github/release.yml"
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
    "configuration_management",
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Where stage 10 ends, every wish with its scenario; copied for each test."""
    work = tmp_path_factory.mktemp("built")
    root = build_python_product(work / "product", branch=FEATURE)
    install_plugins(root)
    for checkpoint in (1, 2, 3):
        approve_checkpoint(root, checkpoint)
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
    found = state["findings"] + state["reported"]
    return state["stage"], state["status"], sorted({f["rule"] for f in found})


def _merge(root, branch, number):
    git(root, "checkout", "-q", "main")
    message = f"Merge pull request #{number} from acme/{branch}"  # GitHub's
    git(root, "merge", "-q", "--no-ff", "-m", message, branch)
    return git_head(root)


def _push(root, tmp_path, monkeypatch, merged, message, people=()):
    """Commit to the release branch; the host shows its pull request reviewed at
    the new head — by the people too, if any — and the feature's pull request merged."""
    if message:
        commit_all(root, message)
    write_report(read_product_config(root))
    head = git_head(root)
    delivery = pull_request(
        1, merged, branch=FEATURE, merged=True, commits=[merged], reviews=[review(AGENT, merged)]
    )
    release = pull_request(
        2,
        head,
        branch=RELEASE,
        files=["releases/1.0.0.yaml"],
        reviews=[review(r, head) for r in (AGENT, *people)],
    )
    tags = {"v6.0.0": git_head(root / ".framework")}
    pulls = [delivery, release, *checkpoint_pulls(root)]
    host = write_host(tmp_path / "release.json", pulls=pulls, tags=tags)
    monkeypatch.setenv("QF_HOST_FILE", str(host))


def _propose(root, tmp_path, monkeypatch):
    """Merge the delivery, then open the release pull request with its record."""
    merged = _merge(root, FEATURE, 1)
    git(root, "checkout", "-q", "-b", RELEASE)
    assert write_release(["--root", str(root)]) == 0
    _push(root, tmp_path, monkeypatch, merged, "chore(release): 1.0.0 #2")
    return merged


def _validate(root, tmp_path, monkeypatch, merged):
    """Deploy the head, run the scenarios there, add the demo's result by hand."""
    deployed = git_head(root)
    args = ["--root", str(root), "--environment", "staging", "--commit", deployed]
    assert write_validation_record(args) == 0
    record = yaml.safe_load((root / RECORD).read_text())
    record["results"].append(
        {"scenario": DEMO, "technique": "guided demo", "result": "pass", "note": "It locked."}
    )
    (root / RECORD).write_text(yaml.safe_dump(record, sort_keys=False))
    _push(root, tmp_path, monkeypatch, merged, "chore(release): validation of 1.0.0 #2")


def _accept(root, tmp_path, monkeypatch, merged):
    """The architect approves the release's head on the host, for the village."""
    _push(root, tmp_path, monkeypatch, merged, None, people=(PERSON,))


def _tag_script(root):
    """The release workflow's tag step, run against this framework."""
    steps = yaml.safe_load((REPO_ROOT / WORKFLOW).read_text())["jobs"]["release"]["steps"]
    (step,) = (s for s in steps if s.get("name") == "Tag the accepted release")
    script = step["run"].replace("python .framework/", f"{sys.executable} {REPO_ROOT}/")
    env = {**os.environ, "GITHUB_OUTPUT": os.devnull}
    return subprocess.run(["bash", "-c", script], cwd=root, capture_output=True, text=True, env=env)


def _checked(root, capsys):
    """The resolver's command as CI runs it: its exit code and the state it
    prints, from one run."""
    capsys.readouterr()
    code = resolve_main(["--root", str(root), "--check"])
    state = json.loads(capsys.readouterr().out)
    return code, (state["stage"], state["status"], sorted({f["rule"] for f in state["findings"]}))


def test_the_village_crew_has_its_method_and_rulebook(product):
    loaded = load_skills(product, STAGE)
    assert Path(loaded["plugin"]["skill_file"]).parent.name == (
        "derive_validation_scenarios_plugin"
    )
    assert [p.split("/")[-2] for p in loaded["framework_skills"]] == ["validate_release_skill"]


def test_a_release_is_validated_and_waits_for_the_architect(product, tmp_path, monkeypatch, capsys):
    merged = _propose(product, tmp_path, monkeypatch)
    assert _state(product) == (
        STAGE,
        "gates_failing",
        ["MISSING_PERSON_APPROVAL", "MISSING_VALIDATION_RECORD"],
    )

    _validate(product, tmp_path, monkeypatch, merged)
    results = yaml.safe_load((product / RECORD).read_text())["results"]
    assert {r["result"] for r in results} == {"pass"} and len(results) == 3
    # the merge waits for the architect, who accepts on behalf of the customer
    assert _checked(product, capsys) == (
        1,
        (STAGE, "awaiting_checkpoint", ["MISSING_PERSON_APPROVAL"]),
    )
    page = (product / ".qf/runs").glob(f"*/{PAGE}")
    assert any("## Validation of release 1.0.0 — staging" in p.read_text() for p in page)

    _accept(product, tmp_path, monkeypatch, merged)
    assert _checked(product, capsys) == (0, (STAGE, "awaiting_checkpoint", []))  # ready to merge

    # After the merge, the release workflow tags it; the tag keeps the record.
    _merge(product, RELEASE, 2)
    config = read_product_config(product)
    assert approval_state(config, 5, "release").status == "approved"
    notes = release_notes(config, "1.0.0")
    assert notes == "Release 1.0.0. Accepted on behalf of Carla Village by @lead-bob, #2."
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    git(product, "remote", "set-url", "--push", "origin", str(origin))
    tagged = _tag_script(product)
    assert tagged.returncode == 0, tagged.stderr
    assert verify_release_evidence_gate.check(read_product_config(product)) == []
