"""gates/sup/verify_history_kept_gate.py — a push to main never rewrites its history."""

import json
import subprocess

import pytest
from product_builder import build_product, commit_all, git_head

from gates.sup.verify_history_kept_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def product(tmp_path):
    root = build_product(tmp_path / "product")
    git(root, "branch", "-M", "main")
    return root


def _push(tmp_path, monkeypatch, before, after, ref="refs/heads/main"):
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {"ref": ref, "before": before, "after": after, "repository": {"default_branch": "main"}}
        )
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))


def _rules(product):
    return [f.rule for f in check(read_product_config(product))]


def test_gate_name_follows_the_convention():
    assert GATE == "verify_history_kept_gate"


def test_a_push_that_adds_commits_passes(product, tmp_path, monkeypatch):
    before = git_head(product)
    (product / "notes.md").write_text("more\n")
    commit_all(product, "docs: more notes #1")
    _push(tmp_path, monkeypatch, before, git_head(product))
    assert _rules(product) == []


def test_a_force_push_that_drops_commits_is_caught(product, tmp_path, monkeypatch):
    (product / "notes.md").write_text("lost\n")
    commit_all(product, "docs: a commit the force-push drops #1")
    before = git_head(product)
    git(product, "reset", "-q", "--hard", "HEAD~1")
    (product / "other.md").write_text("instead\n")
    commit_all(product, "docs: the rewritten history #2")
    _push(tmp_path, monkeypatch, before, git_head(product))

    findings = check(read_product_config(product))

    assert [f.rule for f in findings] == ["MAIN_REWRITTEN"]
    assert before[:7] in findings[0].message


def test_a_lost_commit_unknown_to_the_clone_is_caught(product, tmp_path, monkeypatch):
    _push(tmp_path, monkeypatch, "b" * 40, git_head(product))
    assert _rules(product) == ["MAIN_REWRITTEN"]


@pytest.mark.parametrize(
    ("before", "ref"),
    [("0" * 40, "refs/heads/main"), ("b" * 40, "refs/heads/feature/REQ-0047-x")],
)
def test_a_first_push_or_another_branch_has_nothing_to_compare(
    product, tmp_path, monkeypatch, before, ref
):
    _push(tmp_path, monkeypatch, before, git_head(product), ref)
    assert _rules(product) == []


def test_outside_a_push_there_is_nothing_to_compare(product):
    assert _rules(product) == []
