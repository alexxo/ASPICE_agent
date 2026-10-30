"""agent/render_diagram_review_tool.py — the page a person reads before checkpoint 1."""

import yaml
from product_builder import approve_checkpoint

from agent.render_diagram_review_tool import (
    diagram_review_findings,
    diagram_review_page,
    render,
    render_diagram_review,
)
from tools.read_product_config_tool import read_product_config


def _config(root):
    return read_product_config(root)


def _rules(root):
    return [f.rule for f in diagram_review_findings(_config(root))]


def _add_rule(root):
    path = root / "docs/diagrams/login.invariants.yaml"
    data = yaml.safe_load(path.read_text())
    data["invariants"][0]["statement"] = "After three failed sign-ins the account is locked."
    data["invariants"].append(
        {"id": "INV-2", "statement": "A locked account opens no session.", "constrains": ["x"]}
    )
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def test_the_page_shows_the_pictures_rules_and_wish_links(product):
    page = render(_config(product))
    assert '<a href="login.sequence.html" target="_blank">' in page
    assert '<iframe src="login.sequence.html"' in page
    assert "After five consecutive failed sign-ins the account is locked." in page
    assert "W-02 — Accounts are protected against guessing." in page
    assert "Nothing is marked: no earlier approval of checkpoint 1" in page


def test_a_changed_rule_is_marked_against_the_previous_approval(product):
    """FB-57: a rule changes, the picture does not; the page shows it."""
    approve_checkpoint(product, 1, number=4)
    _add_rule(product)
    page = render(_config(product))
    assert "1 new · 1 changed · 0 removed</b> since the previous approval, #4" in page
    rule = page[page.index("INV-1") : page.index("</tr>", page.index("INV-1"))]
    assert "<del>" in rule and "<ins>three" in rule
    assert '<tr class="term new"><td class="mark">new</td><td class="rule"><div>INV-2' in page


def test_the_page_is_required_and_kept_current_until_approved(product):
    assert _rules(product) == []
    _add_rule(product)
    assert _rules(product) == ["REVIEW_PAGE_OUTDATED"]
    render_diagram_review(product)
    approve_checkpoint(product, 1)
    diagram_review_page(_config(product)).unlink()
    assert _rules(product) == ["MISSING_REVIEW_PAGE"]


def test_the_approval_covers_the_page(product):
    from tools.read_approvals_tool import subject_files

    covered = [_config(product).relative(f) for f in subject_files(_config(product), "diagrams")]
    assert "docs/diagrams/review.html" in covered
