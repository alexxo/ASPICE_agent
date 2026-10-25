"""gates/sup/verify_required_checks_gate.py — the gates run on every change."""

import pytest
from product_builder import build_product

from gates.sup.verify_required_checks_gate import check, gates_job
from tools.read_product_config_tool import read_product_config

CI = ".github/workflows/quality_gates.yml"


@pytest.fixture
def product(tmp_path):
    return build_product(tmp_path / "product")  # with the template, as the setup writes it


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


def _messages(product):
    found = check(read_product_config(product))
    return [f.message for f in found if f.rule == "CI_FILE_NOT_TEMPLATE"]


def _edit(product, old, new):
    ci = product / CI
    text = ci.read_text()
    assert old in text
    ci.write_text(text.replace(old, new, 1))


REPORT_STEP = "      - name: Write the verification report\n"


def test_the_products_own_steps_may_be_added(product):
    toolchain = '      - name: "Install Java"\n        run: echo java\n'
    _edit(product, REPORT_STEP, toolchain + REPORT_STEP)
    assert _rules(product) == []


GATES_STEP = "      - name: Quality gates\n"
TRIGGER = "  pull_request_review:\n    types: [submitted, dismissed]\n"


@pytest.mark.parametrize(
    ("old", "new", "said"),
    [
        ("--check | tee", "--check || true | tee", "the step 'Quality gates' is changed"),
        (GATES_STEP, GATES_STEP + "        continue-on-error: true\n", "may fail without failing"),
        (TRIGGER, "", "it is not triggered on pull_request_review"),
        ("  statuses: write\n", "  statuses: read\n", "permission statuses is not write"),
    ],
)
def test_a_ci_file_that_departs_from_the_template_is_caught(product, old, new, said):
    """FB-45 D3 B: no person reviews the CI file, so the gate keeps it to the template."""
    _edit(product, old, new)
    assert any(said in m for m in _messages(product))


def test_a_step_moved_out_of_order_is_caught(product):
    """The checkpoint-4 review comes after the verification report it reads."""
    text = (product / CI).read_text()
    review = text[text.index('      - name: "Checkpoint-4 review') : text.index(GATES_STEP)]
    _edit(product, review, "")
    _edit(product, REPORT_STEP, review + REPORT_STEP)
    assert any("out of the template's order" in m for m in _messages(product))
