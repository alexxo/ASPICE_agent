"""gates/sup/check_config_items_gate.py — every configuration item exists and is tracked."""

import shutil

import pytest
from product_builder import QF, build_product, commit_all, complete_config_items

from gates.sup.check_config_items_gate import check
from tools.read_product_config_tool import read_product_config


@pytest.fixture
def product(tmp_path):
    qf = {**QF, "config_items": ["runbooks"]}
    return complete_config_items(build_product(tmp_path / "product", qf=qf))


def rules(root):
    return sorted((f.rule, f.file) for f in check(read_product_config(root)))


def test_every_item_tracked_passes(product):
    assert rules(product) == []


def test_a_missing_item_is_caught(product):
    shutil.rmtree(product / "observability")
    assert rules(product) == [("MISSING_CONFIG_ITEM", "observability")]


def test_an_empty_folder_is_missing(product):
    shutil.rmtree(product / "observability")
    (product / "observability").mkdir()
    assert rules(product) == [("MISSING_CONFIG_ITEM", "observability")]


def test_the_products_own_item_counts_too(product):
    shutil.rmtree(product / "runbooks")
    assert rules(product) == [("MISSING_CONFIG_ITEM", "runbooks")]


def test_an_item_never_committed_is_caught(tmp_path):
    root = complete_config_items(build_product(tmp_path / "p"))
    (root / "st").rename(root / "st-old")
    (root / "st").mkdir()
    (root / "st/test_x.py").write_text("x\n")
    assert ("UNTRACKED_CONFIG_ITEM", "st") in rules(root)


def test_an_untracked_file_inside_an_item_is_caught(product):
    (product / "src/auth.py").write_text("x = 1\n")
    found = check(read_product_config(product))
    assert [(f.rule, f.file) for f in found] == [("UNTRACKED_CONFIG_ITEM", "src")]
    assert "src/auth.py" in found[0].message


@pytest.mark.parametrize("pattern", ["observability/", "/observability", "*.yaml"])
def test_an_ignored_item_is_caught(product, pattern):
    (product / ".gitignore").write_text(pattern + "\n")
    commit_all(product, "chore: ignore #1")
    found = rules(product)
    assert found and all(r == "UNTRACKED_CONFIG_ITEM" for r, _ in found)


def test_ignored_files_inside_an_item_are_fine(product):
    (product / ".gitignore").write_text("__pycache__/\n")
    (product / "src/__pycache__").mkdir()
    (product / "src/__pycache__/a.pyc").write_text("")
    commit_all(product, "chore: ignore caches #1")
    assert rules(product) == []


def test_a_product_without_git_is_caught(tmp_path):
    root = build_product(tmp_path / "plain", git=False)
    assert [f.rule for f in check(read_product_config(root))] == ["NOT_A_GIT_REPOSITORY"]


def test_the_scenarios_folder_is_required_once_it_exists(product):
    # The one item written after stage 10: the scenarios gate requires it at stage 11.
    shutil.rmtree(product / "validation/scenarios")
    commit_all(product, "test: drop the scenarios #1")
    assert rules(product) == []
    (product / "validation/scenarios").mkdir(parents=True)
    (product / "validation/scenarios/test_sign_in.py").write_text("# @wish[W-01]\n")
    assert rules(product) == [("UNTRACKED_CONFIG_ITEM", "validation/scenarios")]
