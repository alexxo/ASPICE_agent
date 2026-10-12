"""gates/sup/check_track_rule_gate.py, verify_architecture_tests_gate.py — the tracks apart."""

import subprocess

import pytest
from product_builder import build_product, commit_all

from gates.sup import check_track_rule_gate, verify_architecture_tests_gate
from tools.read_product_config_tool import read_product_config


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def change(root, *paths):
    for path in paths:
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(f"{path}\n")
    commit_all(root, "feat: change REQ-0047")


@pytest.fixture
def product(tmp_path, monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    root = build_product(tmp_path / "product")
    git(root, "branch", "-M", "main")
    return root


def rules(root, gate=check_track_rule_gate, base=None):
    return sorted((f.rule, f.file) for f in gate.check(read_product_config(root), base=base))


def on(root, name):
    git(root, "checkout", "-q", "-b", name)


def test_a_feature_pull_request_passes_both(product):
    on(product, "feature/REQ-0047-lockout")
    change(product, "src/auth/lockout.py", "docs/design/auth.md", "st/test_lockout.py")
    assert rules(product) == []
    assert rules(product, verify_architecture_tests_gate) == []


def test_an_architecture_pull_request_on_its_branch_passes_both(product):
    on(product, "arch/session-store")
    change(product, "docs/architecture/session.md", "docs/requirements/session.md")
    assert rules(product) == []
    assert rules(product, verify_architecture_tests_gate) == []


@pytest.mark.parametrize(
    "path",
    [
        "docs/design/auth.md",
        "docs/verification-plan.md",
        "docs/configuration.md",
        "it/test_flow.py",
        "st/test_lockout.py",
        "observability/alerts/a.yaml",
    ],
)
def test_the_feature_track_in_an_architecture_pull_request_is_caught(product, path):
    on(product, "arch/session-store")
    change(product, "docs/architecture/session.md", path)
    assert rules(product) == [("MIXED_TRACKS", path)]


def test_the_architecture_off_an_arch_branch_is_caught(product):
    on(product, "feature/REQ-0047-lockout")
    change(product, "docs/architecture/stack.yaml")
    assert rules(product) == [("ARCHITECTURE_OFF_BRANCH", "docs/architecture/stack.yaml")]


def test_code_in_an_architecture_pull_request_is_caught(product):
    on(product, "arch/session-store")
    change(product, "docs/architecture/session.md", "src/session/store.py")
    assert rules(product) == []
    assert rules(product, verify_architecture_tests_gate) == [
        ("CODE_IN_ARCHITECTURE_PR", "src/session/store.py")
    ]


def test_a_deleted_architecture_file_counts(product):
    change(product, "docs/architecture/session.md")
    on(product, "arch/drop-session-store")
    git(product, "rm", "-q", "docs/architecture/session.md")
    change(product, "src/session/store.py")
    assert rules(product, verify_architecture_tests_gate) == [
        ("CODE_IN_ARCHITECTURE_PR", "src/session/store.py")
    ]


def test_only_the_pull_requests_commits_count(product):
    change(product, "docs/architecture/session.md", "src/session/store.py")  # merged before
    on(product, "feature/REQ-0047-lockout")
    change(product, "src/auth/lockout.py")
    assert rules(product) == []
    assert rules(product, verify_architecture_tests_gate) == []
    assert rules(product, base="HEAD~2") == [
        ("ARCHITECTURE_OFF_BRANCH", "docs/architecture/session.md")
    ]


def test_ci_names_the_pull_requests_branch(product, monkeypatch):
    on(product, "arch/session-store")
    change(product, "docs/architecture/session.md")
    git(product, "checkout", "-q", "--detach")
    assert rules(product) == [("ARCHITECTURE_OFF_BRANCH", "docs/architecture/session.md")]
    monkeypatch.setenv("GITHUB_HEAD_REF", "arch/session-store")
    assert rules(product) == []
