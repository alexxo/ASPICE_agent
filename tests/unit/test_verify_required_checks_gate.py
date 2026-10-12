"""gates/sup/verify_required_checks_gate.py — no gate can be switched off."""

import shutil

import pytest
from product_builder import CODEOWNERS, PROTECTION, add_origin, build_product, write_host

from gates.sup.verify_required_checks_gate import check, gates_job, owned
from tools.read_product_config_tool import read_product_config

CI = ".github/workflows/quality_gates.yml"


@pytest.fixture
def product(tmp_path, repo_root):
    root = build_product(tmp_path / "product")
    add_origin(root)
    (root / ".github/workflows").mkdir(parents=True)
    shutil.copy(repo_root / "templates/github/quality_gates.yml", root / CI)
    (root / ".github/CODEOWNERS").write_text(CODEOWNERS)
    return root


def _rules(product, tmp_path, monkeypatch, protection=PROTECTION):
    host = write_host(tmp_path / "host.json", protection=protection)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return sorted(f.rule for f in check(read_product_config(product)))


def test_a_protected_branch_requiring_the_gates_passes(product, tmp_path, monkeypatch):
    assert _rules(product, tmp_path, monkeypatch) == []


def test_the_template_names_its_gates_job(repo_root):
    assert gates_job(repo_root / "templates/github/quality_gates.yml") == "gates"


def test_an_unprotected_branch_is_caught(product, tmp_path, monkeypatch):
    assert _rules(product, tmp_path, monkeypatch, protection=None) == ["BRANCH_NOT_PROTECTED"]
    no_review = {**PROTECTION, "reviews_required": False}
    assert _rules(product, tmp_path, monkeypatch, no_review) == ["BRANCH_NOT_PROTECTED"]


def test_gates_that_are_not_required_are_caught(product, tmp_path, monkeypatch):
    optional = {**PROTECTION, "required_checks": ["lint"]}
    assert _rules(product, tmp_path, monkeypatch, optional) == ["CHECK_NOT_REQUIRED"]


def test_a_ci_file_that_runs_no_gates_is_caught(product, tmp_path, monkeypatch):
    (product / CI).write_text("on: push\njobs:\n  build:\n    steps:\n      - run: make\n")
    assert _rules(product, tmp_path, monkeypatch) == ["CHECK_NOT_REQUIRED"]


@pytest.mark.parametrize("off", ["code_owner_reviews", "enforce_admins"])
def test_a_bypassable_protection_is_caught(product, tmp_path, monkeypatch, off):
    weak = {**PROTECTION, off: False}
    assert _rules(product, tmp_path, monkeypatch, weak) == ["PROTECTION_BYPASSABLE"]


def test_every_guarded_path_needs_an_owner(product, tmp_path, monkeypatch):
    (product / ".github/CODEOWNERS").write_text("/docs/architecture/ @lead-bob\n")
    assert _rules(product, tmp_path, monkeypatch) == ["UNOWNED_PATH", "UNOWNED_PATH"]
    (product / ".github/CODEOWNERS").unlink()
    assert _rules(product, tmp_path, monkeypatch) == ["UNOWNED_PATH"] * 3


@pytest.mark.parametrize(
    ("rules", "path", "expected"),
    [
        ([("*", ["@a"])], ".gitmodules", True),
        ([("/.github/", ["@a"])], ".github/workflows/q.yml", True),
        ([(".github/workflows/*.yml", ["@a"])], ".github/workflows/q.yml", True),
        ([("docs/", ["@a"])], "docs/architecture/", True),
        ([("/src/", ["@a"])], ".gitmodules", False),
        ([("*", ["@a"]), ("/.gitmodules", [])], ".gitmodules", False),  # the last match wins
        ([("/docs/architecture/", ["@a"])], "docs/architecture/", True),
        ([("architecture.md", ["@a"])], "docs/architecture/", False),
    ],
)
def test_codeowners_follow_githubs_matching(rules, path, expected):
    assert owned(rules, path) is expected
