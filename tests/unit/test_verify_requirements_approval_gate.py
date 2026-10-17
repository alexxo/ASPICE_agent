"""gates/swe/verify_requirements_approval_gate.py — requirements approved before the design."""

from datetime import datetime, timedelta, timezone

from product_builder import STACK, build_product, detailed_design_doc

from agent.record_checkpoint_tool import record_checkpoint
from gates.swe.verify_requirements_approval_gate import GATE, check
from tools.read_product_config_tool import read_product_config

EARLIER = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _approve(root, when=EARLIER):
    record_checkpoint(root, 2, "approved", "Alex", "architect", now=when)


def test_gate_name_follows_the_convention():
    assert GATE == "verify_requirements_approval_gate"


def test_without_a_design_nothing_has_to_be_approved_yet(product):
    assert _rules(product) == []


def test_a_stack_alone_needs_the_approval(tmp_path):
    root = build_product(tmp_path, stack=STACK)
    (root / "docs/architecture/auth-flow.md").unlink()
    assert _rules(root) == ["MISSING_APPROVAL"]


def test_a_detailed_design_alone_needs_the_approval(tmp_path):
    """Detailed design files are derived from the requirements too (stage 4)."""
    root = build_product(tmp_path, stack=STACK, detailed_design=detailed_design_doc())
    (root / "docs/architecture/auth-flow.md").unlink()
    (root / "docs/architecture/stack.yaml").unlink()
    assert _rules(root) == ["MISSING_APPROVAL"]


def test_a_design_after_a_current_approval_passes(tmp_path):
    root = build_product(tmp_path, stack=STACK)
    _approve(root)
    assert _rules(root) == []


def test_a_changed_requirement_makes_the_approval_outdated(tmp_path):
    root = build_product(tmp_path, stack=STACK)
    _approve(root)
    login = next((root / "docs/requirements").glob("*.md"))
    login.write_text(login.read_text() + "\n")
    assert _rules(root) == ["APPROVAL_OUTDATED"]


def test_an_approval_given_after_the_design_is_reported(tmp_path):
    root = build_product(tmp_path, stack=STACK)
    _approve(root, when=datetime.now(timezone.utc) + timedelta(days=1))
    assert _rules(root) == ["APPROVED_TOO_LATE"]


def test_requirements_without_their_review_page_are_reported(tmp_path):
    root = build_product(tmp_path, review_pages=False, git=False)
    (finding,) = check(read_product_config(root))
    assert (finding.rule, finding.file) == ("MISSING_REVIEW_PAGE", "docs/requirements/review.html")


def test_a_review_page_older_than_the_requirements_is_reported(product):
    login = product / "docs/requirements/login.md"
    login.write_text(login.read_text().replace("Five failed", "Three failed"))
    assert _rules(product) == ["REVIEW_PAGE_OUTDATED"]


def test_a_changed_diagram_withdraws_the_approval(tmp_path):
    """The requirements are reviewed again against the new diagram (rule 25)."""
    root = build_product(tmp_path, stack=STACK)
    _approve(root)
    links = root / "docs/diagrams/login.wishes.yaml"
    links.write_text(links.read_text() + "\n")
    assert _rules(root) == ["APPROVAL_OUTDATED"]


def test_an_approved_review_page_is_held_by_the_approval(tmp_path, monkeypatch):
    """A later framework version may render differently: the approval still counts."""
    from agent import render_review_tool

    root = build_product(tmp_path, stack=STACK)
    _approve(root)
    monkeypatch.setattr(render_review_tool, "PAGE", render_review_tool.PAGE + "<!-- v2 -->\n")
    assert _rules(root) == []
