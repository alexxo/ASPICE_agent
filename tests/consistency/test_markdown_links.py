"""Layer 2 — every internal markdown link in this tree resolves inside it.

External links (http, mailto), pure anchors, placeholders and inline code spans
(a regular expression is not a link) are skipped; every
other link must point at a file or directory that exists in this tree, so no
document depends on a file outside it.
"""

import re

import pytest

pytestmark = pytest.mark.layer2

EXCLUDE = (".venv", ".git", "node_modules", ".pytest_cache")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CODE_SPAN_RE = re.compile(r"`[^`\n]+`")


def _md_files(repo_root):
    return [f for f in repo_root.rglob("*.md") if not any(p in EXCLUDE for p in f.parts)]


def test_internal_markdown_links_resolve_inside_the_tree(repo_root):
    files = _md_files(repo_root)
    assert files, "no markdown files found"
    broken = []
    for f in files:
        text = CODE_SPAN_RE.sub("", f.read_text(encoding="utf-8"))
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#", "<")):
                continue
            path = target.split("#", 1)[0].split(" ", 1)[0].strip()
            if not path or any(c in path for c in "*{}"):
                continue
            resolved = (f.parent / path).resolve()
            if not resolved.exists() or repo_root.resolve() not in resolved.parents:
                broken.append(f"{f.relative_to(repo_root)} -> {target}")
    assert not broken, "links that do not resolve inside the tree:\n  " + "\n  ".join(broken)
