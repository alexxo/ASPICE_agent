"""Render the requirements review page a person reads before checkpoint 2.

<requirements_dir>/review.html shows every requirement, each system-level one
(shaded) followed by the software-level ones refining it (indented), then the
glossary terms. Every field of every record is shown; glossary terms are in
italics, each acceptance criterion coloured by its case, a threshold in bold.

What is new, changed or removed is marked against the previous approval of
checkpoint 2: the latest approval of other content than the page shows, its
files read from git at the commit that added it. A changed row marks the words
removed and added; a summary counts the changes and names the diagram files
changed since that approval, which the requirements are derived from. At the
first approval nothing is marked.

The page depends only on the files it shows and that commit — no clock, no
machine, a fixed order — so the approval gate renders it again and compares
byte for byte, and record_checkpoint_tool refuses an approval on a page the
files no longer render (§ 5 stages 1 and 2, rules 22–25). The agent never
writes it by hand; it renders it, and commits it, before the person reviews.
The diagrams are reviewed on their pictures; they have no review page.

    python agent/render_review_tool.py [--root PRODUCT]
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.check_approval_order_tool import in_git  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_approvals_tool import approval_state, sha256, subject_files  # noqa: E402
from tools.read_product_config_tool import ProductConfig, read_product_config  # noqa: E402
from tools.read_requirements_tool import read_requirements  # noqa: E402
from tools.read_yaml_blocks_tool import (  # noqa: E402
    YamlReadError,
    read_yaml_blocks,
    read_yaml_file,
)
from tools.validate_contract_tool import contract_path, validate  # noqa: E402

__all__ = ["render", "render_review", "review_page", "review_page_findings"]

# The requirement's columns: one field each, then the measure, then every other field.
COLUMNS = [
    ("UID", ["uid"]),
    ("Kind", ["kind"]),
    ("Criticality", ["criticality"]),
    ("Statement", ["statement"]),
    ("Derived from", ["derived_from"]),
    ("Acceptance criteria", ["acceptance_criteria"]),
    ("Measure", ["metric", "threshold", "measurement_method", "events", "watched_by"]),
]


def review_page(config: ProductConfig) -> Path:
    return config.requirements_dir / "review.html"


def render_review(root: Path) -> Path:
    """Write the review page and return its path."""
    config = read_product_config(root)
    page = review_page(config)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(render(config), encoding="utf-8")
    return page


def render(config: ProductConfig) -> str:
    """The review page's text, from the files as they are and the previous approval."""
    baseline, commit, recorded = _baseline(config)
    old: list[dict] | None = None
    if commit is not None:
        with tempfile.TemporaryDirectory() as folder:
            old = _model(_config_at(config, commit, Path(folder)))
    sections = _model(config)
    rendered = [_section(s, old) for s in sections]
    for section in old or []:  # the glossary removed since the approval
        if section["key"] not in {s["key"] for s in sections}:
            rendered.append(_section({**section, "rows": []}, [section]))
    body = "".join(text for text, _ in rendered)
    if commit is None:
        summary = "Nothing is marked: no earlier approval of checkpoint 2 to compare with."
    else:
        counts = {mark: sum(c[mark] for _, c in rendered) for mark in ("new", "changed", "removed")}
        summary = (
            f"<b>{counts['new']} new · {counts['changed']} changed · {counts['removed']} "
            f"removed</b> since the previous approval, {html.escape(baseline)}, at commit "
            f"<code>{commit}</code>. {_diagrams_changed(config, recorded)}"
            '<label><input type="checkbox" '
            "onchange=\"document.body.classList.toggle('only', this.checked)\"> "
            "Show changes only</label>"
        )
    return PAGE.format(summary=summary, body=body)


def review_page_findings(config: ProductConfig) -> list[Finding]:
    """The page missing, or different from a fresh render while it awaits approval.

    Once a current approval covers the page, its hashes hold it: a later framework
    version that renders differently does not withdraw an approval."""
    page = review_page(config)
    shown = config.relative(page)
    if not page.is_file():
        return [
            Finding(
                "MISSING_REVIEW_PAGE",
                shown,
                None,
                "No review page for the requirements; render it with "
                "agent/render_review_tool.py and commit it, so the person reviews a page, "
                "not the raw files.",
            )
        ]
    if approval_state(config, 2, "requirements").status == "approved":
        return []
    if page.read_text(encoding="utf-8") != render(config):
        return [
            Finding(
                "REVIEW_PAGE_OUTDATED",
                shown,
                None,
                "The review page differs from what the files render now (stale or edited "
                "by hand); render it again with agent/render_review_tool.py and commit it.",
            )
        ]
    return []


# --- the model: sections of rows, each row a key and its fields -------------------------


def _model(config: ProductConfig) -> list[dict]:
    blocks = read_requirements(config)
    rows = [_block_row(b.file, b.block) for b in blocks]
    readable = [r for r in rows if "uid" in r["fields"]]
    system = sorted(
        (r for r in readable if r["fields"].get("level") != "software"), key=lambda r: r["key"]
    )
    ordered = []
    for parent in system:
        ordered.append(parent)
        ordered += sorted(
            (r for r in readable if r["fields"].get("refines") == parent["key"]),
            key=lambda r: r["key"],
        )
    ordered += [r for r in rows if r not in ordered]  # unrefined or unreadable: at the end
    shown = [field for _, fields in COLUMNS for field in fields]
    rest = [f for f in _fields("requirement", ordered) if f not in shown]
    sections = [
        {
            "key": "requirements",
            "heading": "Requirements",
            "columns": [*COLUMNS, ("Details", rest)],
            "rows": ordered,
        }
    ]
    glossary = config.glossary_file
    if glossary.is_file():
        shown_as = config.relative(glossary)
        terms = [_block_row(shown_as, b) for b in read_yaml_blocks(glossary, "glossary_term")]
        sections.append(
            {
                "key": "glossary",
                "heading": f"Glossary ({shown_as})",
                "columns": [(_label(f), [f]) for f in _fields("glossary_term", terms)],
                "rows": terms,
            }
        )
    return sections


def _block_row(file: str, block) -> dict:
    data = block.data if isinstance(block.data, dict) else None
    if data is None:
        problem = block.error or "not a mapping"
        return {"key": f"{file}:{block.line}", "fields": {"problem": f"unreadable: {problem}"}}
    key = data.get("uid") or data.get("term") or f"{file}:{block.line}"
    return {"key": str(key), "fields": data}


def _fields(contract: str, rows: list[dict]) -> list[str]:
    """The contract's fields in its own order, then any other field a row holds."""
    schema = json.loads(contract_path(contract).read_text())
    properties = schema["properties"]
    present = [k for row in rows for k in row["fields"]]
    return [k for k in properties if k in present] + sorted(set(present) - set(properties))


def _label(field: str) -> str:
    return field.replace("_", " ").capitalize()


# --- the baseline: the previous approval's files, from git -------------------------------


def _baseline(config: ProductConfig) -> tuple[str, str | None, dict[str, str]]:
    """The previous approval, the commit that added it and the hashes it records: the
    latest approval of other content than the page shows. No commit when there is
    none, or it is not committed."""
    shown = {
        config.relative(f): sha256(f)
        for f in subject_files(config, "requirements")
        if f.suffix != ".html"
    }
    folder = config.approvals_dir
    pattern = "*-checkpoint-2-requirements.yaml"
    for path in sorted(folder.glob(pattern), reverse=True) if folder.is_dir() else []:
        try:
            data = read_yaml_file(path)
        except YamlReadError:
            continue
        if validate(data, "approval") or data["decision"] != "approved":
            continue
        recorded = {
            s["path"]: s["sha256"] for s in data["subject"] if not s["path"].endswith(".html")
        }
        if recorded == shown:
            continue  # the approval of what the page shows, not the previous one
        commit = _added_in(config.root, path)
        return config.relative(path), commit, recorded if commit else {}
    return "", None, {}


def _diagrams_changed(config: ProductConfig, recorded: dict[str, str]) -> str:
    """The diagram files changed since the previous approval, if it recorded them."""
    folder = config.relative(config.diagrams_dir) + "/"
    before = {p: h for p, h in recorded.items() if p.startswith(folder)}
    if not before:
        return ""
    now = {
        config.relative(f): sha256(f)
        for f in subject_files(config, "requirements")
        if config.relative(f).startswith(folder)
    }
    changed = sorted(p for p in set(before) | set(now) if before.get(p) != now.get(p))
    if not changed:
        return "The diagrams are unchanged. "
    names = ", ".join(f"<code>{html.escape(p)}</code>" for p in changed)
    return f"<b>The diagrams changed:</b> {names} — check the requirements derived from them. "


def _added_in(root: Path, file: Path) -> str | None:
    if not in_git(root):
        return None
    added = _git(root, "log", "--diff-filter=A", "--format=%H", "--", str(file.resolve()))
    commits = added.split()
    return commits[-1] if commits else None


def _config_at(config: ProductConfig, commit: str, folder: Path) -> ProductConfig:
    """The configuration over a copy of the requirements and the glossary, as they were
    at a commit."""
    shown = [config.requirements_dir, config.glossary_file]
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
    paths = {
        f.name: folder / config.relative(getattr(config, f.name))
        for f in dataclasses.fields(config)
        if isinstance(getattr(config, f.name), Path) and f.name != "root"
    }
    return dataclasses.replace(config, root=folder, **paths)


def _git(root: Path, *args: str) -> str:
    run = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    return run.stdout if run.returncode == 0 else ""


# --- the page ----------------------------------------------------------------------------

# Marks travel through escaping as control characters, then become tags.
INS, INS_END, DEL, DEL_END = "\x01", "\x02", "\x03", "\x04"
TAGS = {INS: "<ins>", INS_END: "</ins>", DEL: "<del>", DEL_END: "</del>"}
# A glossary term is one token, so a mark never cuts through its italics.
TERM = r"(?<![A-Za-z0-9_])_[^_\n]+?_(?![A-Za-z0-9_])"
TOKEN = re.compile(rf"{TERM}|\s+|[^\s_]+|\S")


def _section(section: dict, old: list[dict] | None) -> tuple[str, dict[str, int]]:
    """The section's table, and how many of its rows are new, changed and removed."""
    before = next((s for s in old or [] if s["key"] == section["key"]), None)
    previous = {r["key"]: r["fields"] for r in (before or {}).get("rows", [])}
    columns = section["columns"]
    counts = {"new": 0, "changed": 0, "removed": 0}
    head = "".join(f"<th>{html.escape(label)}</th>" for label, _ in [("Change", []), *columns])
    parts = [
        f"<section>\n<h2>{html.escape(section['heading'])}</h2>\n"
        f"<table>\n<thead><tr>{head}</tr></thead>\n<tbody>\n"
    ]
    keys = set()
    for row in section["rows"]:
        keys.add(row["key"])
        was = previous.get(row["key"])
        if old is None:
            mark = ""
        elif was is None:
            mark = "new"
        else:
            mark = "changed" if was != row["fields"] else "unchanged"
        if mark in counts:
            counts[mark] += 1
        parts.append(_row(mark, columns, row["fields"], was if mark == "changed" else None))
    for key, fields in previous.items():
        if key not in keys:
            counts["removed"] += 1
            parts.append(_row("removed", columns, fields, None))
    parts.append("</tbody>\n</table>\n</section>\n")
    return "".join(parts), counts


def _row(mark: str, columns: list, fields: dict, was: dict | None) -> str:
    level = "software" if fields.get("level") == "software" else "system"
    if "uid" not in fields:
        level = "term"
    cells = [f'<td class="mark">{"" if mark == "unchanged" else mark}</td>']
    for label, names in columns:
        lines = _lines(fields, names, len(names) > 1)
        if was is not None:
            lines = _marked(_lines(was, names, len(names) > 1), lines)
        elif mark == "removed":
            lines = [(cls, DEL + text + DEL_END) for cls, text in lines]
        cls = f' class="{label.lower().replace(" ", "-")}"'
        cells.append(f"<td{cls}>{_cell(lines)}</td>")
    classes = f"{level} {mark}".strip()
    if fields.get("criticality") == "high":
        classes += " high"
    return f'<tr class="{classes}">{"".join(cells)}</tr>\n'


def _lines(fields: dict, names: list[str], labelled: bool) -> list[tuple[str, str]]:
    """A cell as lines of plain text, each with its class: a list one item per line,
    a mapping as key: value pairs; several fields each under its label."""
    lines = []
    for name in names:
        if name not in fields:
            continue
        value = fields[name]
        prefix = f"{_label(name)}: " if labelled else ""
        cls = "threshold" if name == "threshold" else ""
        items = value if isinstance(value, list) else [value]
        for item in items:
            if name == "acceptance_criteria" and isinstance(item, dict):
                steps = "; ".join(f"{k} {_text(v)}" for k, v in item.items() if k != "case")
                text = f"{item.get('case', '')} — {steps}"
                lines.append((f"case {item.get('case', '')}", prefix + text))
            else:
                lines.append((cls, prefix + _text(item)))
    return lines


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return "; ".join(f"{k.replace('_', ' ')}: {_text(v)}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(_text(v) for v in value)
    return str(value)


def _marked(old: list[tuple[str, str]], new: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The new lines with what changed from the old ones marked: a line added or
    removed as a whole, the words in a changed line."""
    out = []
    matcher = difflib.SequenceMatcher(None, [t for _, t in old], [t for _, t in new], False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            out += new[j1:j2]
            continue
        olds, news = old[i1:i2], new[j1:j2]
        for k in range(max(len(olds), len(news))):
            o = olds[k] if k < len(olds) else None
            n = news[k] if k < len(news) else None
            if n is None:
                out.append((f"{o[0]} gone".strip(), DEL + o[1] + DEL_END))
            elif o is None:
                out.append((f"{n[0]} added".strip(), INS + n[1] + INS_END))
            else:
                out.append((n[0], _words(o[1], n[1])))
    return out


def _words(old: str, new: str) -> str:
    a, b = TOKEN.findall(old), TOKEN.findall(new)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, False).get_opcodes():
        if op in ("delete", "replace"):
            out.append(DEL + "".join(a[i1:i2]) + DEL_END)
        if op in ("insert", "replace"):
            out.append(INS + "".join(b[j1:j2]) + INS_END)
        if op == "equal":
            out.append("".join(b[j1:j2]))
    return "".join(out)


def _cell(lines: list[tuple[str, str]]) -> str:
    return "".join(
        f'<div class="{cls}">{_formatted(text)}</div>' if cls else f"<div>{_formatted(text)}</div>"
        for cls, text in lines
    )


def _formatted(text: str) -> str:
    """Escaped, glossary terms in italics, the change marks as tags."""
    out = re.sub(TERM, lambda m: f"<i>{m.group()[1:-1]}</i>", html.escape(text))
    return re.sub("[\x01-\x04]", lambda m: TAGS[m.group()], out)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Checkpoint 2 — the requirements</title>
<style>
body {{ font: 14px system-ui, sans-serif; margin: 1.5rem; color: #111; background: #fff; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.5rem 0 1.5rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left;
  vertical-align: top; }}
th {{ background: #eee; position: sticky; top: 0; }}
section {{ overflow-x: auto; }}
tr.system td {{ background: #f3f6fb; font-weight: 500; }}
tr.software td.uid {{ padding-left: 1.6rem; }}
tr.high td.criticality {{ color: #b00; font-weight: 600; }}
td.mark {{ font-size: 12px; font-weight: 600; }}
tr.new td.mark {{ box-shadow: inset 5px 0 #1f6feb; color: #1f6feb; }}
tr.changed td.mark {{ box-shadow: inset 5px 0 #b8860b; color: #b8860b; }}
tr.removed td.mark {{ box-shadow: inset 5px 0 #888; color: #666; }}
tr.removed td {{ color: #777; }}
.case {{ margin: 2px 0; padding-left: 4px; border-left: 3px solid; }}
.case.happy {{ border-color: #070; }}
.case.edge {{ border-color: #a60; }}
.case.error {{ border-color: #b00; }}
.threshold {{ font-weight: 700; }}
i {{ color: #036; }}
ins {{ background: #d7f5dd; color: #05631d; }}
del {{ background: #fde0e0; color: #a40000; }}
.added {{ background: #d7f5dd; }}
.gone {{ background: #fde0e0; }}
.summary {{ background: #fffbe6; border: 1px solid #e6d58a; padding: 0.5rem; }}
body.only tr.unchanged {{ display: none; }}
</style>
</head>
<body>
<h1>Checkpoint 2 — the requirements</h1>
<p>Each system-level requirement (shaded), followed by the software-level ones refining it
(indented); then the glossary. <i>Italics</i>: a glossary term. Rendered by the framework's
render_review_tool from the committed files; never edited by hand.</p>
<p class="summary">{summary}</p>
{body}</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    print(render_review(args.root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
