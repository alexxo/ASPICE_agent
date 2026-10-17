"""agent/render_review_tool.py — the page a person reads before checkpoints 1 and 2."""

import html
import json
from datetime import datetime, timezone

import pytest
from product_builder import build_product, commit_all

from agent.record_checkpoint_tool import record_checkpoint
from agent.render_review_tool import main, render, render_review, review_page
from tools.read_product_config_tool import read_product_config
from tools.read_requirements_tool import read_requirements
from tools.read_yaml_blocks_tool import read_yaml_blocks, read_yaml_file

NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)


def _page(root, checkpoint):
    return render(read_product_config(root), checkpoint)


def _approve(root, checkpoint, hour=9):
    record_checkpoint(root, checkpoint, "approved", "Alex", "architect", now=NOW.replace(hour=hour))
    commit_all(root, f"checkpoint {checkpoint} approved")


def _leaves(value):
    """Every scalar a field holds, as it appears on the page."""
    if isinstance(value, dict):
        return [leaf for v in value.values() for leaf in _leaves(v)]
    if isinstance(value, list):
        return [leaf for v in value for leaf in _leaves(v)]
    return [html.escape(str(value))]


def _fields(value):
    if isinstance(value, dict):
        return [*value, *(k for v in value.values() for k in _fields(v))]
    if isinstance(value, list):
        return [k for v in value for k in _fields(v)]
    return []


def test_the_pages_are_written_next_to_what_they_show(product):
    config = read_product_config(product)
    assert review_page(config, 1) == product / "docs/diagrams/review.html"
    assert review_page(config, 2) == product / "docs/requirements/review.html"
    assert render_review(product, 2).read_text() == _page(product, 2)


def test_the_page_is_its_source(product):
    """No clock, no machine: the same files render the same bytes, wherever they are."""
    assert _page(product, 1) == _page(product, 1)
    assert (product / "docs/diagrams/review.html").read_text() == _page(product, 1)


def test_every_field_of_every_requirement_and_term_is_shown(product):
    """The framework test of rule 24: no field of a contract is left off the page."""
    config = read_product_config(product)
    page = _page(product, 2)
    records = [b.data for b in read_requirements(config)]
    records += [b.data for b in read_yaml_blocks(config.glossary_file, "glossary_term")]
    for record in records:
        for field in _fields(record):
            assert html.escape(field) in page, field
        for leaf in _leaves(record):
            assert leaf in page, leaf


def test_every_element_wish_link_and_invariant_is_shown(product):
    page = _page(product, 1)
    folder = product / "docs/diagrams"
    for spec in folder.glob("*.json"):
        for collection in json.loads(spec.read_text()).values():
            for item in collection if isinstance(collection, list) else []:
                assert html.escape(item["id"]) in page and html.escape(item["label"]) in page
    for file in [*folder.glob("*.wishes.yaml"), *folder.glob("*.invariants.yaml")]:
        data = read_yaml_file(file)
        for leaf in _leaves(data.get("links") or data.get("invariants")):
            assert leaf in page, (file.name, leaf)
    assert '<iframe src="login.sequence.html"' in page  # next to its picture


def test_each_system_requirement_is_followed_by_the_ones_refining_it(product):
    page = _page(product, 2)
    tree = ["REQ-0011", "REQ-0049", "REQ-0012", "REQ-0047", "REQ-0048", "REQ-0013", "REQ-0051"]
    positions = [page.index(f"<td>{uid}</td>") for uid in tree]
    assert positions == sorted(positions)


def test_at_the_first_approval_nothing_is_marked(product):
    page = _page(product, 1)
    assert "Nothing is marked" in page
    assert 'class="mark' not in page.split("<body>")[1]


def test_changes_are_marked_against_the_previous_approval(product):
    _approve(product, 1)
    spec = product / "docs/diagrams/login.sequence.json"
    data = json.loads(spec.read_text())
    data["messages"][1]["label"] = "session open"  # changed
    data["messages"].append(  # new
        {"id": "retry", "from": "web-app", "to": "auth-service", "y": 220, "label": "retry"}
    )
    data["participants"].pop(0)  # removed: web-app
    spec.write_text(json.dumps(data, indent=2))
    page = _page(product, 1)
    assert "Marked against the previous approval" in page
    section = page.split("<h2>login.sequence.json</h2>")[1].split("</section>")[0]
    assert '<tr class="changed"><td class="mark changed">changed</td><td>session-opened' in section
    assert '<td class="differs">session open</td>' in section
    assert '<tr class="new"><td class="mark new">new</td><td>retry' in section
    assert '<tr class="removed"><td class="mark removed">removed</td><td>web-app' in section
    other = page.split("<h2>auth-flow.architecture.json</h2>")[1].split("</section>")[0]
    assert 'class="mark' not in other


def test_the_approval_of_what_the_page_shows_is_not_its_baseline(product):
    """Re-rendering after the approval keeps the page the person approved."""
    before = _page(product, 2)
    _approve(product, 2)
    assert _page(product, 2) == before


def test_a_second_approval_compares_with_the_first(product):
    _approve(product, 2, hour=9)
    login = product / "docs/requirements/login.md"
    login.write_text(login.read_text().replace("Five failed", "Three failed"))
    render_review(product, 2)
    commit_all(product, "requirements changed")
    _approve(product, 2, hour=10)
    page = _page(product, 2)
    assert "2026-10-04T090000Z-checkpoint-2-requirements.yaml" in page
    assert '<td class="differs">Three failed sign-ins cause a _lockout_.</td>' in page


def test_only_checkpoints_1_and_2_have_a_review_page(product, capsys):
    with pytest.raises(ValueError, match="only 1 and 2"):
        render_review(product, 3)
    assert main(["--root", str(product), "--checkpoint", "3"]) == 1
    assert "only 1 and 2" in capsys.readouterr().err


def test_the_command_writes_the_page(tmp_path, capsys):
    root = build_product(tmp_path, review_pages=False, git=False)
    assert main(["--root", str(root), "--checkpoint", "1"]) == 0
    assert capsys.readouterr().out.strip().endswith("docs/diagrams/review.html")
