"""gates/sup/verify_required_checks_gate.py — the gates run on every change."""

import shutil

import pytest
from product_builder import build_product

from gates.sup.verify_required_checks_gate import check, gates_job
from tools.read_product_config_tool import read_product_config

CI = ".github/workflows/quality_gates.yml"


@pytest.fixture
def product(tmp_path, repo_root):
    root = build_product(tmp_path / "product")
    (root / ".github/workflows").mkdir(parents=True)
    shutil.copy(repo_root / "templates/github/quality_gates.yml", root / CI)
    return root


def _rules(product):
    return sorted(f.rule for f in check(read_product_config(product)))


def test_a_ci_file_that_runs_the_gates_passes(product):
    assert _rules(product) == []


def test_the_template_names_its_gates_job(repo_root):
    assert gates_job(repo_root / "templates/github/quality_gates.yml") == "gates"


def test_a_ci_file_that_runs_no_gates_is_caught(product):
    (product / CI).write_text("on: push\njobs:\n  build:\n    steps:\n      - run: make\n")
    assert _rules(product) == ["MISSING_GATES_JOB"]


def test_a_missing_ci_file_is_caught(product):
    (product / CI).unlink()
    assert _rules(product) == ["MISSING_GATES_JOB"]


def test_no_host_is_read(product, monkeypatch):
    """No token and no host file: the gate still decides, from the CI file alone."""
    monkeypatch.delenv("QF_HOST_FILE", raising=False)
    monkeypatch.delenv("QF_HOST_TOKEN", raising=False)
    assert _rules(product) == []
