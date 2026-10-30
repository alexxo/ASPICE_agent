"""Render the diagrams review page a person reads before checkpoint 1.

<diagrams_dir>/review.html shows, per diagram, its pictures — each linked and
shown in place, as the diagram plugin rendered it — then its rules
(<id>.invariants.yaml) and which wishes each of its elements realises
(<id>.wishes.yaml), each wish with its statement. The pictures cannot show the
rules or the wish links, yet the approval covers them.

What is new, changed or removed is marked against the previous approval of
checkpoint 1: the latest merged checkpoint/1 pull request that approved other
content than the page shows, its files read from git at the head it approved.
A changed rule marks the
words removed and added; a picture is marked when its diagram changed. At the
first approval nothing is marked.

The page depends only on the files it shows and that commit, so the diagram
contract gate renders it again and compares byte for byte, and
record_checkpoint_tool refuses to merge an approval of a page the files no
longer render
(§ 5 stages 1 and 2, rules 21–25). The agent never writes it by hand; it
renders it, and commits it, before the person reviews.

    python agent/render_diagram_review_tool.py [--root PRODUCT] [--no-open]

Run from the command line, it opens the page in the browser of this computer
(never in CI or a test run, nor with --no-open).
"""

from __future__ import annotations

import argparse
import dataclasses
import html
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.render_review_tool import STYLE as TABLES  # noqa: E402
from agent.render_review_tool import _git, _section  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_approvals_tool import approval_state, previous_approval, sha256  # noqa: E402
from tools.read_product_config_tool import ProductConfig, read_product_config  # noqa: E402
from tools.read_yaml_blocks_tool import (  # noqa: E402
    YamlReadError,
    read_yaml_blocks,
    read_yaml_file,
)
from tools.render_page_tool import open_page  # noqa: E402
from tools.render_page_tool import page as layout  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

__all__ = ["diagram_review_findings", "diagram_review_page", "render", "render_diagram_review"]


def diagram_review_page(config: ProductConfig) -> Path:
    return config.diagrams_dir / "review.html"


def render_diagram_review(root: Path) -> Path:
    """Write the review page and return its path."""
    config = read_product_config(root)
    page = diagram_review_page(config)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(render(config), encoding="utf-8")
    return page


def render(config: ProductConfig) -> str:
    """The review page's text, from the files as they are and the previous approval."""
    previous = previous_approval(config, 1, "diagrams")
    commit = previous.head if previous else None
    old = None
    if commit is not None:
        with tempfile.TemporaryDirectory() as folder:
            old = _model(_files_at(config, commit, Path(folder)))
    now = _model(config)
    counts = {"new": 0, "changed": 0, "removed": 0}
    parts = []
    for name in sorted(set(now) | set(old or {})):
        diagram = now.get(name)
        was = (old or {}).get(name)
        if diagram is None:
            counts["removed"] += 1
            parts.append(f'<section class="removed">\n<h2>{html.escape(name)} — removed</h2>\n')
            parts.append("</section>\n")
            continue
        parts.append(f"<section>\n<h2>{html.escape(name)}</h2>\n")
        for picture, sha in diagram["pictures"].items():
            mark = _mark(old, (was or {}).get("pictures", {}).get(picture), sha)
            if mark in counts:
                counts[mark] += 1
            link = html.escape(picture)
            parts.append(
                f'<div class="picture {mark}"><p><span class="mark">{_shown(mark)}</span>'
                f'<a href="{link}" target="_blank">{link}</a></p>'
                f'<iframe src="{link}" title="{link}"></iframe></div>\n'
            )
        for key in ("rules", "links"):
            section = diagram[key]
            if not section["rows"] and not (was and was[key]["rows"]):
                continue  # no such file, then or now
            before = [was[key]] if was else ([] if old is not None else None)
            text, found = _section(section, before, {})
            parts.append(text)
            for mark in counts:
                counts[mark] += found[mark]
        parts.append("</section>\n")
    if commit is None:
        summary = "Nothing is marked: no earlier approval of checkpoint 1 to compare with."
    else:
        summary = (
            f"<b>{counts['new']} new · {counts['changed']} changed · {counts['removed']} "
            f"removed</b> since the previous approval, #{previous.number}, at commit "
            f"<code>{commit}</code>."
        )
    return layout(TITLE, LEAD, summary, "".join(parts), STYLE)


def diagram_review_findings(config: ProductConfig) -> list[Finding]:
    """The page missing, or different from a fresh render while it awaits approval."""
    folder = config.diagrams_dir
    if not (folder.is_dir() and any(folder.glob("*.json"))):
        return []  # nothing drawn yet
    page = diagram_review_page(config)
    shown = config.relative(page)
    if not page.is_file():
        return [
            Finding(
                "MISSING_REVIEW_PAGE",
                shown,
                None,
                "No review page for the diagrams; render it with "
                "agent/render_diagram_review_tool.py and commit it, so the person sees the "
                "rules and wish links next to the pictures.",
            )
        ]
    if approval_state(config, 1, "diagrams").status == "approved":
        return []
    if page.read_text(encoding="utf-8") != render(config):
        return [
            Finding(
                "REVIEW_PAGE_OUTDATED",
                shown,
                None,
                "The diagrams review page differs from what the files render now (stale or "
                "edited by hand); render it again with agent/render_diagram_review_tool.py and "
                "commit it.",
            )
        ]
    return []


# --- the model: per diagram its pictures, rules and wish links -----------------------------


def _model(config: ProductConfig) -> dict[str, dict]:
    folder = config.diagrams_dir
    wishes = _wishes(config)
    diagrams: dict[str, dict] = {}

    def diagram(name: str) -> dict:
        return diagrams.setdefault(
            name,
            {
                "pictures": {},
                "rules": _empty("rules", f"Rules of {name} ({name}.invariants.yaml)", RULES),
                "links": _empty("links", f"Wish links of {name} ({name}.wishes.yaml)", LINKS),
            },
        )

    for spec in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        diagram(spec.name.split(".")[0])["pictures"][spec.with_suffix(".html").name] = sha256(spec)
    for path in sorted(folder.glob("*.invariants.yaml")) if folder.is_dir() else []:
        data = _read(path, "invariants")
        rows = diagram(path.name.split(".")[0])["rules"]["rows"]
        for rule in data.get("invariants", []) if data else []:
            rows.append({"key": rule["id"], "fields": dict(rule)})
    for path in sorted(folder.glob("*.wishes.yaml")) if folder.is_dir() else []:
        data = _read(path, "diagram_wishes")
        rows = diagram(path.name.split(".")[0])["links"]["rows"]
        for element, linked in (data or {}).get("links", {}).items():
            told = [f"{w} — {wishes[w]}" if w in wishes else w for w in linked]
            rows.append({"key": element, "fields": {"element": element, "wishes": told}})
    return diagrams


RULES = [("Rule", ["id"]), ("Statement", ["statement"]), ("Constrains", ["constrains"])]
LINKS = [("Element", ["element"]), ("Realises", ["wishes"])]


def _empty(key: str, heading: str, columns: list) -> dict:
    return {"key": key, "heading": heading, "columns": columns, "rows": []}


def _read(path: Path, contract: str) -> dict | None:
    try:
        data = read_yaml_file(path)
    except YamlReadError:
        return None
    return data if isinstance(data, dict) and not validate(data, contract) else None


def _wishes(config: ProductConfig) -> dict[str, str]:
    path = config.wishes_file
    blocks = read_yaml_blocks(path, "wish") if path.is_file() else []
    return {
        str(b.data["id"]): str(b.data.get("statement", ""))
        for b in blocks
        if isinstance(b.data, dict) and b.data.get("id")
    }


def _mark(old: dict | None, was: str | None, sha: str) -> str:
    if old is None:
        return ""
    if was is None:
        return "new"
    return "changed" if was != sha else "unchanged"


def _shown(mark: str) -> str:
    return f"{mark} " if mark in ("new", "changed") else ""


# --- the previous approval's files, from git -----------------------------------------------


def _files_at(config: ProductConfig, commit: str, folder: Path) -> ProductConfig:
    """The configuration over a copy of the diagrams and the wishes, as they were at a
    commit."""
    shown = [config.diagrams_dir, config.wishes_file]
    listed = _git(
        config.root, "ls-tree", "-r", "--name-only", commit, "--", *map(config.relative, shown)
    )
    for name in listed.splitlines():
        if name.endswith(".html"):
            continue
        content = subprocess.run(
            ["git", "-C", str(config.root), "show", f"{commit}:./{name}"],
            capture_output=True,
            check=False,
        ).stdout
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return dataclasses.replace(
        config,
        root=folder,
        diagrams_dir=folder / config.relative(config.diagrams_dir),
        wishes_file=folder / config.relative(config.wishes_file),
    )


TITLE = "Checkpoint 1 — the diagrams"
LEAD = (
    "Each diagram: its pictures, then its rules and the wishes each element realises — the "
    "pictures cannot show them, yet your approval covers them. Rendered by the framework's "
    "render_diagram_review_tool from the committed files; never edited by hand."
)
STYLE = (
    TABLES
    + """\
iframe { width: 100%; height: 480px; border: 1px solid #ccc; }
.picture.new .mark { color: #1f6feb; font-weight: 600; }
.picture.changed .mark { color: #b8860b; font-weight: 600; }
"""
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args(argv)
    page = render_diagram_review(args.root)
    print(page if args.no_open else open_page(page))
    return 0


if __name__ == "__main__":
    sys.exit(main())
