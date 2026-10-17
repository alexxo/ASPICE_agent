"""gates/swe/verify_diagram_approval_gate.py — diagrams approved before requirements are derived."""

from datetime import datetime, timedelta, timezone

from product_builder import build_product, commit_all

from agent.record_checkpoint_tool import record_checkpoint
from gates.swe.verify_diagram_approval_gate import GATE, check
from tools.read_product_config_tool import read_product_config

EARLIER = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _approve(root, when=EARLIER):
    record_checkpoint(root, 1, "approved", "Alex", "architect", now=when)


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


def test_changes_requested_count_as_no_approval(product):
    record_checkpoint(product, 1, "changes-requested", "Alex", "architect", "Fix it.", now=EARLIER)
    assert _rules(product) == ["MISSING_APPROVAL"]


def test_an_approval_of_older_diagram_content_is_reported(product):
    _approve(product)
    spec = product / "docs/diagrams/login.sequence.json"
    spec.write_text(spec.read_text().replace("submit", "send"))
    assert _rules(product) == ["APPROVAL_OUTDATED"]


def test_an_approval_given_after_the_requirements_is_reported(product):
    """The requirements were committed before the diagrams were approved."""
    _approve(product, when=datetime.now(timezone.utc) + timedelta(days=1))
    assert _rules(product) == ["APPROVED_TOO_LATE"]


def test_uncommitted_requirements_count_as_derived_now(product):
    _approve(product)
    (product / "docs/requirements/more.md").write_text("# More\n")
    assert _rules(product) == []


def test_outside_a_git_repository_the_order_cannot_be_shown(tmp_path):
    root = build_product(tmp_path, git=False)
    _approve(root)
    assert _rules(root) == ["NOT_A_GIT_REPOSITORY"]


def test_a_later_commit_of_the_requirements_keeps_their_first_date(product):
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
