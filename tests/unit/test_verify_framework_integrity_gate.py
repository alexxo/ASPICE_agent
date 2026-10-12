"""gates/sup/verify_framework_integrity_gate.py — the framework pinned, untouched and released."""

import subprocess

import pytest
from product_builder import (
    FRAMEWORK_REPO,
    add_framework,
    build_product,
    commit_all,
    make_framework,
    write_host,
)

from gates.sup.verify_framework_integrity_gate import check
from tools.read_product_config_tool import read_product_config


@pytest.fixture
def framework(tmp_path):
    return tmp_path / "framework", make_framework(tmp_path / "framework")


@pytest.fixture
def product(tmp_path, framework):
    root = build_product(tmp_path / "product")
    add_framework(root, framework[0])
    return root


def _rules(product, tmp_path, monkeypatch, tags):
    host = write_host(tmp_path / "host.json", tags=tags)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return sorted(f.rule for f in check(read_product_config(product)))


def test_a_released_untouched_pin_passes(product, framework, tmp_path, monkeypatch):
    assert _rules(product, tmp_path, monkeypatch, {"v6.0.0": framework[1]}) == []


def test_a_framework_that_is_no_submodule_is_not_pinned(tmp_path, monkeypatch, framework):
    root = build_product(tmp_path / "plain")
    (root / ".framework").mkdir()
    (root / ".framework/README.md").write_text("copied in\n")
    commit_all(root, "copy the framework")
    assert _rules(root, tmp_path, monkeypatch, {"v6.0.0": framework[1]}) == ["FRAMEWORK_NOT_PINNED"]


def test_a_local_change_to_the_framework_is_caught(product, framework, tmp_path, monkeypatch):
    (product / ".framework/README.md").write_text("A gate switched off.\n")
    tags = {"v6.0.0": framework[1]}
    assert _rules(product, tmp_path, monkeypatch, tags) == ["FRAMEWORK_MODIFIED"]


def test_a_checkout_away_from_the_pin_is_caught(product, framework, tmp_path, monkeypatch):
    fw = product / ".framework"
    (fw / "gate.py").write_text("print('pass')\n")
    commit_all(fw, "local gate")
    tags = {"v6.0.0": framework[1]}
    assert _rules(product, tmp_path, monkeypatch, tags) == ["FRAMEWORK_MODIFIED"]


def test_an_unreleased_pin_is_caught(product, tmp_path, monkeypatch):
    assert _rules(product, tmp_path, monkeypatch, {"v5.0.0": "0" * 40}) == [
        "FRAMEWORK_NOT_RELEASED"
    ]


def test_the_release_is_read_from_the_frameworks_repository(product, framework, tmp_path):
    url = subprocess.run(
        ["git", "-C", str(product), "config", "-f", ".gitmodules", "--get-regexp", "url"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert FRAMEWORK_REPO in url
