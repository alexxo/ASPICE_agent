"""gates/swe/verify_diagram_approval_gate.py — diagrams approved before requirements are derived."""

from product_builder import approve_checkpoint, build_product, commit_all

from agent.render_diagram_review_tool import render_diagram_review
from gates.swe.verify_diagram_approval_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _approve(root):
    approve_checkpoint(root, 1)


def test_gate_name_follows_the_convention():
    assert GATE == "verify_diagram_approval_gate"


def test_without_requirements_nothing_has_to_be_approved_yet(tmp_path):
    root = build_product(tmp_path, requirements={}, git=False)
    assert _rules(root) == []


def test_requirements_after_a_current_approval_pass(product):
    _approve(product)
    assert _rules(product) == []


def test_requirements_without_an_approval_are_reported(product):
    assert _rules(product) == ["MISSING_APPROVAL"]


def test_an_approval_of_older_diagram_content_is_reported(product):
    _approve(product)
    spec = product / "docs/diagrams/login.sequence.json"
    spec.write_text(spec.read_text().replace("submit", "send"))
    assert _rules(product) == ["APPROVAL_OUTDATED"]


def test_corrected_diagrams_approved_again_pass(product):
    """Rule 25: a later approval covers the fix."""
    _approve(product)
    spec = product / "docs/diagrams/login.sequence.json"
    spec.write_text(spec.read_text().replace("submit", "send"))
    commit_all(product, "correct the diagram")
    render_diagram_review(product)  # against the first approval
    _approve(product)
    assert _rules(product) == []


def test_uncommitted_requirements_count_as_derived_now(product):
    _approve(product)
    (product / "docs/requirements/more.md").write_text("# More\n")
    assert _rules(product) == []


def test_outside_a_git_repository_no_approval_can_be_shown(tmp_path):
    root = build_product(tmp_path, git=False)
    assert _rules(root) == ["NOT_A_GIT_REPOSITORY"]


def test_a_later_commit_of_the_requirements_needs_no_new_approval(product):
    _approve(product)
    (product / "docs/requirements/login.md").write_text(
        (product / "docs/requirements/login.md").read_text() + "\n"
    )
    commit_all(product, "edit requirements")
    assert _rules(product) == []


def test_the_diagrams_need_no_review_page(tmp_path):
    """The person reviews the diagrams on their pictures (§ 5 stages 1 and 2, rule 22)."""
    root = build_product(tmp_path, requirements={}, review_pages=False, git=False)
    assert _rules(root) == []
