"""gates/sup/check_commit_conventions_gate.py — commits and branches named by convention."""

import json
import subprocess

import pytest
from product_builder import build_product, commit_all

from gates.sup.check_commit_conventions_gate import check
from tools.read_product_config_tool import read_product_config


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def commit(root, message, path="src/auth/lockout.py"):
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(message + "\n")
    commit_all(root, message)


@pytest.fixture
def product(tmp_path, monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    root = build_product(tmp_path / "product")  # one commit on main: already merged
    git(root, "branch", "-M", "main")
    git(root, "checkout", "-q", "-b", "feature/REQ-0047-lockout")
    return root


def rules(root, base=None):
    return sorted(f.rule for f in check(read_product_config(root), base=base))


@pytest.mark.parametrize(
    "message",
    [
        "feat(auth): lock the account after 5 failures REQ-0047",
        "fix: count each failure once (#12)",
        "refactor(auth)!: split the counter\n\nServes REQ-0047.",
        'Revert "feat(auth): lock the account REQ-0047"',
    ],
)
def test_a_conventional_commit_naming_its_requirement_passes(product, message):
    commit(product, message)
    assert rules(product) == []


@pytest.mark.parametrize(
    "message",
    ["REQ-0047 lock the account", "Feat: lock the account REQ-0047", "wip(auth): REQ-0047"],
)
def test_a_commit_that_is_not_conventional_is_caught(product, message):
    commit(product, message)
    assert rules(product) == ["NOT_CONVENTIONAL"]


@pytest.mark.parametrize("message", ["feat(auth): lock the account", "fix: see PR&#12"])
def test_a_commit_naming_no_requirement_or_issue_is_caught(product, message):
    commit(product, message)
    assert rules(product) == ["MISSING_REQUIREMENT_TOKEN"]


def test_only_the_pull_requests_commits_are_read(product):
    commit(product, "feat(auth): lock REQ-0047")
    assert rules(product) == []  # the builder's commit on main is not conventional


def test_merge_commits_are_not_read(product):
    commit(product, "feat(auth): lock REQ-0047")
    git(product, "checkout", "-q", "main")
    commit(product, "fix: elsewhere REQ-0048", "src/other.py")
    git(product, "checkout", "-q", "feature/REQ-0047-lockout")
    who = ("-c", "user.name=t", "-c", "user.email=t@e.org")
    git(product, *who, "merge", "-q", "--no-edit", "main")
    assert rules(product) == []


def test_the_given_base_bounds_the_range(product, monkeypatch):
    commit(product, "wip REQ-0047")
    commit(product, "feat(auth): lock REQ-0047")
    assert rules(product) == ["NOT_CONVENTIONAL"]
    assert rules(product, base="HEAD~1") == []
    monkeypatch.setenv("QF_BASE", "HEAD~1")
    assert rules(product) == []


@pytest.mark.parametrize(
    "name",
    [
        "feature/REQ-0047-lockout",
        "bugfix/REQ-0048-double-count",
        "arch/session-store",
        "checkpoint/2",
        "release/v1.4.0",  # no longer a meaningful prefix
        "chore/ignore-archify",  # work that serves no requirement: any name is free
        "wip",
    ],
)
def test_a_branch_without_a_meaningful_prefix_or_with_its_form_passes(product, name):
    git(product, "checkout", "-q", "-B", name)
    assert rules(product) == []


@pytest.mark.parametrize(
    "name", ["arch/REQ-0047", "arch/Session_Store", "checkpoint/4", "checkpoint/two"]
)
def test_an_arch_or_checkpoint_branch_off_its_form_is_caught(product, name):
    git(product, "checkout", "-q", "-b", name)
    assert rules(product) == ["BAD_BRANCH_NAME"]


def test_the_main_branch_is_exempt_and_reads_no_commit(product):
    git(product, "checkout", "-q", "main")
    assert rules(product) == []


def test_ci_names_the_pull_requests_branch(product, monkeypatch):
    git(product, "checkout", "-q", "--detach")
    monkeypatch.setenv("GITHUB_HEAD_REF", "checkpoint/9")
    assert rules(product) == ["BAD_BRANCH_NAME"]


def test_a_product_without_git_is_caught(tmp_path):
    root = build_product(tmp_path / "plain", git=False)
    assert rules(root) == ["NOT_A_GIT_REPOSITORY"]


def _push_to_main(tmp_path, monkeypatch, before):
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "ref": "refs/heads/main",
                "before": before,
                "after": "",
                "repository": {"default_branch": "main"},
            }
        )
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))


def test_a_commit_pushed_to_main_must_name_its_reason(product, tmp_path, monkeypatch):
    git(product, "checkout", "-q", "main")
    before = subprocess.run(
        ["git", "-C", str(product), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    commit(product, "fix: a quick change straight on main")
    _push_to_main(tmp_path, monkeypatch, before)
    assert rules(product) == ["MISSING_REQUIREMENT_TOKEN"]


def test_on_main_outside_a_push_nothing_is_checked(product):
    git(product, "checkout", "-q", "main")
    commit(product, "fix: a quick change straight on main")
    assert rules(product) == []
