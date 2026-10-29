"""Layer 2 — every page a person reads comes from the one layout, nothing folded.

§ 5 *One layout for the person*: tools/render_page_tool.py writes the page frame
and the card; no other tool writes an HTML page of its own, and nothing a person
reads is folded away.
"""

import pytest

pytestmark = pytest.mark.layer2

LAYOUT = "tools/render_page_tool.py"


def _sources(repo_root):
    paths = [*repo_root.glob("agent/*.py"), *repo_root.glob("tools/*.py")]
    paths += repo_root.glob("gates/*/*.py")
    return {p.relative_to(repo_root).as_posix(): p.read_text() for p in sorted(paths)}


def test_only_the_layout_writes_a_page(repo_root):
    writers = [
        name
        for name, text in _sources(repo_root).items()
        if "<!doctype html" in text.lower() and name != LAYOUT
    ]
    assert writers == []


def test_nothing_a_person_reads_is_folded(repo_root):
    folded = [name for name, text in _sources(repo_root).items() if "<details" in text]
    assert folded == []


def test_every_page_tool_uses_the_layout(repo_root):
    for name in [
        "agent/render_review_tool.py",
        "agent/render_diagram_review_tool.py",
        "agent/render_decisions_tool.py",
        "agent/ask_person_tool.py",
    ]:
        assert "tools.render_page_tool" in (repo_root / name).read_text(), name
