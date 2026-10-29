"""tools/read_requirements_tool.py — which requirements are critical, and which changed."""

import subprocess

from product_builder import build_product, commit_all

from tools.read_product_config_tool import read_product_config
from tools.read_requirements_tool import changed_since, critical


def _head(root):
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def test_a_high_or_security_requirement_is_critical():
    assert critical({"criticality": "high", "kind": "functional"})
    assert critical({"criticality": "low", "kind": "security"})
    assert not critical({"criticality": "medium", "kind": "functional"})


def test_the_requirements_added_or_changed_since_a_commit(tmp_path):
    root = build_product(tmp_path)
    config = read_product_config(root)
    before = _head(root)
    assert changed_since(config, before) == []
    login = root / "docs/requirements/login.md"
    login.write_text(
        login.read_text().replace("The web app shows a sign-in form.", "The web app shows a form.")
    )
    commit_all(root, "change request #37")
    assert changed_since(config, before) == ["REQ-0011"]


def test_a_commit_git_cannot_show_changes_nothing_known(tmp_path):
    config = read_product_config(build_product(tmp_path))
    assert changed_since(config, "0" * 40) is None
