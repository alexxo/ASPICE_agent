"""agent/render_review_tool.py — the requirements page a person reads before checkpoint 2."""

import html
import re
from datetime import datetime, timezone

from product_builder import build_product, commit_all

from agent.record_checkpoint_tool import record_checkpoint
from agent.render_review_tool import main, render, render_review, review_page
from tools.read_product_config_tool import read_product_config
from tools.read_requirements_tool import read_requirements
from tools.read_yaml_blocks_tool import read_yaml_blocks

NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)


def _page(root):
    return render(read_product_config(root))


def _approve(root, hour=9):
    record_checkpoint(root, 2, "approved", "Alex", "architect", now=NOW.replace(hour=hour))
    commit_all(root, "checkpoint 2 approved")


def _leaves(value):
    """Every scalar a field holds, as it appears on the page (a term in italics)."""
    if isinstance(value, dict):
        return [leaf for v in value.values() for leaf in _leaves(v)]
    if isinstance(value, list):
        return [leaf for v in value for leaf in _leaves(v)]
    text = html.escape(str(value))
    return [re.sub(r"(?<![A-Za-z0-9_])_([^_\n]+?)_(?![A-Za-z0-9_])", r"<i>\1</i>", text)]


def _fields(value):
    if isinstance(value, dict):
        return [*value, *(k for v in value.values() for k in _fields(v))]
    if isinstance(value, list):
        return [k for v in value for k in _fields(v)]
    return []


def _row(page, uid):
    return next(r for r in page.split("<tr ") if f'<td class="uid"><div>{uid}' in r)


def _change(root, old, new):
    login = root / "docs/requirements/login.md"
    login.write_text(login.read_text().replace(old, new))


def test_the_page_is_written_next_to_the_requirements(product):
    config = read_product_config(product)
    assert review_page(config) == product / "docs/requirements/review.html"
    assert render_review(product).read_text() == _page(product)


def test_the_page_is_its_source(product):
    """No clock, no machine: the same files render the same bytes, wherever they are."""
    assert _page(product) == _page(product)
    assert (product / "docs/requirements/review.html").read_text() == _page(product)


def test_every_field_of_every_requirement_and_term_is_shown(product):
    """The framework test of rule 24: no field of a contract is left off the page."""
    config = read_product_config(product)
    page = _page(product)
    records = [b.data for b in read_requirements(config)]
    records += [b.data for b in read_yaml_blocks(config.glossary_file, "glossary_term")]
    for record in records:
        for field in _fields(record):
            assert field.replace("_", " ").lower() in page.lower(), field
        for leaf in _leaves(record):
            assert leaf in page, leaf


def test_each_system_requirement_is_followed_by_the_ones_refining_it(product):
    page = _page(product)
    tree = ["REQ-0011", "REQ-0049", "REQ-0012", "REQ-0047", "REQ-0048", "REQ-0013", "REQ-0051"]
    positions = [page.index(f'<td class="uid"><div>{uid}</div>') for uid in tree]
    assert positions == sorted(positions)
    assert _row(page, "REQ-0012").startswith('class="system')
    assert _row(page, "REQ-0047").startswith('class="software')


def test_the_page_is_readable(product):
    """Headers in words, terms in italics, each case coloured, the threshold in bold."""
    page = _page(product)
    assert "<th>Acceptance criteria</th>" in page and "acceptance_criteria" not in page
    assert "<i>" in _row(page, "REQ-0047")
    assert '<div class="case happy">happy — ' in page
    assert '<div class="case error">error — ' in page
    assert '<div class="threshold">Threshold: ' in page


def test_at_the_first_approval_nothing_is_marked(product):
    page = _page(product)
    assert "Nothing is marked" in page
    assert "<ins>" not in page and "<del>" not in page


def test_changes_are_marked_word_by_word_against_the_previous_approval(product):
    _approve(product)
    _change(product, "Five failed", "Three failed")
    page = _page(product)
    assert "0 new · 1 changed · 0 removed" in page
    row = _row(page, "REQ-0047")
    assert row.startswith('class="software changed')
    assert "<del>Five</del><ins>Three</ins> failed" in row
    assert _row(page, "REQ-0012").startswith('class="system unchanged')
    assert "Show changes only" in page


def test_a_new_and_a_removed_requirement_are_marked(product):
    _approve(product)
    _change(product, "uid: REQ-0051", "uid: REQ-0052")
    page = _page(product)
    assert "1 new · 0 changed · 1 removed" in page
    assert _row(page, "REQ-0052").startswith('class="software new')
    assert _row(page, "<del>REQ-0051</del>").startswith('class="software removed')


def test_the_diagrams_changed_since_the_approval_are_named(product):
    """The requirements are derived from them: the reviewer checks them again (rule 25)."""
    _approve(product)
    assert "The diagrams are unchanged" not in _page(product)  # the approval of what it shows
    _change(product, "Five failed", "Three failed")
    assert "The diagrams are unchanged" in _page(product)
    spec = product / "docs/diagrams/login.sequence.json"
    spec.write_text(spec.read_text().replace("submit", "send"))
    page = _page(product)
    assert "<b>The diagrams changed:</b> <code>docs/diagrams/login.sequence.json</code>" in page


def test_the_approval_of_what_the_page_shows_is_not_its_baseline(product):
    """Re-rendering after the approval keeps the page the person approved."""
    before = _page(product)
    _approve(product)
    assert _page(product) == before


def test_a_second_approval_compares_with_the_first(product):
    _approve(product, hour=9)
    _change(product, "Five failed", "Three failed")
    render_review(product)
    commit_all(product, "requirements changed")
    _approve(product, hour=10)
    _change(product, "Three failed", "Four failed")
    page = _page(product)
    assert "2026-10-04T100000Z-checkpoint-2-requirements.yaml" in page
    assert "<del>Three</del><ins>Four</ins> failed" in page


def test_the_command_writes_the_page(tmp_path, capsys):
    root = build_product(tmp_path, review_pages=False, git=False)
    assert main(["--root", str(root)]) == 0
    assert capsys.readouterr().out.strip().endswith("docs/requirements/review.html")
