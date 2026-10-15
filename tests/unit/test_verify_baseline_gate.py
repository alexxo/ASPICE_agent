"""gates/sup/verify_baseline_gate.py — every release a complete, consistent baseline."""

import subprocess

import pytest
import yaml
from product_builder import (
    add_framework,
    build_product,
    commit_all,
    complete_config_items,
    make_framework,
    tag_release,
    write_host,
)

from gates.sup.verify_baseline_gate import check
from tools.read_product_config_tool import read_product_config
from tools.write_release_tool import main as write_release

RECORD = "releases/1.0.0.yaml"


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def product(tmp_path, monkeypatch):
    framework = make_framework(tmp_path / "framework")
    root = build_product(tmp_path / "product")
    git(root, "branch", "-M", "main")
    add_framework(root, tmp_path / "framework")
    complete_config_items(root)
    host = write_host(tmp_path / "host.json", tags={"v6.0.0": framework})
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return root


def propose(root):
    """The release pull request's commit: the record write_release_tool writes."""
    git(root, "checkout", "-q", "-b", "release/v1.0.0")
    assert write_release(["--root", str(root)]) == 0
    commit_all(root, "chore(release): 1.0.0 #1")


def merge_and_tag(root):
    git(root, "checkout", "-q", "main")
    git(
        root,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@e.org",
        "merge",
        "-q",
        "--no-ff",
        "--no-edit",
        "release/v1.0.0",
    )
    tag_release(root, "1.0.0")


def edit(root, **fields):
    record = yaml.safe_load((root / RECORD).read_text())
    record.update(fields)
    (root / RECORD).write_text(yaml.safe_dump(record, sort_keys=False))


def rules(root):
    return sorted((f.rule, f.file) for f in check(read_product_config(root)))


def test_a_product_before_its_first_release_passes(product):
    assert rules(product) == []


def test_a_proposed_release_written_by_the_tool_passes(product):
    propose(product)
    assert rules(product) == []


def test_a_tagged_release_on_main_passes(product):
    propose(product)
    merge_and_tag(product)
    assert rules(product) == []


def test_a_chosen_version_is_caught(product):
    propose(product)
    (product / RECORD).rename(product / "releases/2.0.0.yaml")
    record = yaml.safe_load((product / "releases/2.0.0.yaml").read_text())
    record["version"] = "2.0.0"
    (product / "releases/2.0.0.yaml").write_text(yaml.safe_dump(record))
    assert rules(product) == [("WRONG_VERSION", "releases/2.0.0.yaml")]


def test_a_record_named_after_another_version_is_caught(product):
    propose(product)
    (product / RECORD).rename(product / "releases/1.0.1.yaml")
    assert rules(product) == [("INCOMPLETE_RELEASE_RECORD", "releases/1.0.1.yaml")]


def test_a_record_off_its_contract_is_caught(product):
    propose(product)
    edit(product, plugins={"archify": "3.0.1"})
    assert rules(product) == [("INCOMPLETE_RELEASE_RECORD", RECORD)]


def test_an_item_left_out_of_the_changes_is_caught(product):
    propose(product)
    record = yaml.safe_load((product / RECORD).read_text())
    edit(product, changed=[i for i in record["changed"] if i != "src"])
    found = check(read_product_config(product))
    assert [f.rule for f in found] == ["INCOMPLETE_RELEASE_RECORD"]
    assert "missing src" in found[0].message


def test_a_framework_other_than_the_pin_is_caught(product):
    propose(product)
    edit(product, framework="v5.0.0")
    found = check(read_product_config(product))
    assert [f.rule for f in found] == ["INCOMPLETE_RELEASE_RECORD"]
    assert "pinned at v6.0.0" in found[0].message


def test_the_next_release_follows_the_commits_since_the_last(product):
    propose(product)
    merge_and_tag(product)
    git(product, "checkout", "-q", "-b", "feature/REQ-0047-lockout")
    (product / "src/lockout.py").write_text("x = 1\n")
    commit_all(product, "feat(auth): lock the account REQ-0047")
    git(product, "checkout", "-q", "-b", "release/v1.1.0")
    assert write_release(["--root", str(product)]) == 0
    record = yaml.safe_load((product / "releases/1.1.0.yaml").read_text())
    assert record["changed"] == ["src"]
    commit_all(product, "chore(release): 1.1.0 #2")
    assert rules(product) == []


def test_a_lightweight_tag_is_caught(product):
    propose(product)
    git(product, "checkout", "-q", "main")
    git(product, "merge", "-q", "release/v1.0.0")
    tag_release(product, "1.0.0", annotated=False)
    assert rules(product) == [("TAG_NOT_ANNOTATED", ".")]


def test_a_tag_off_the_main_branch_is_caught(product):
    propose(product)
    tag_release(product, "1.0.0")  # on the release branch, never merged
    git(product, "checkout", "-q", "main")
    assert rules(product) == [("TAG_NOT_ON_MAIN", ".")]


def test_a_tag_without_its_record_or_an_item_is_caught(product):
    git(product, "rm", "-q", "-r", "observability")
    commit_all(product, "chore: drop observability #1")
    tag_release(product, "1.0.0")
    assert rules(product) == [
        ("INCOMPLETE_RELEASE_RECORD", RECORD),
        ("MISSING_CONFIG_ITEM", "observability"),
    ]


def test_a_product_without_git_is_caught(tmp_path):
    root = build_product(tmp_path / "plain", git=False)
    assert [f.rule for f in check(read_product_config(root))] == ["NOT_A_GIT_REPOSITORY"]


def test_a_moved_release_tag_is_caught(product):
    propose(product)
    merge_and_tag(product)
    commit_all(product, "fix: a later change #2")
    git(
        product,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@e.org",
        "tag",
        "-f",
        "-a",
        "v1.0.0",
        "-m",
        "moved",
    )
    assert rules(product) == [("TAG_MOVED", RECORD)]
