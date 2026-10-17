"""Render the review page a person reads before checkpoint 1 or 2.

    checkpoint 1   <diagrams_dir>/review.html       every diagram's elements, invariants
                                                    and wish links, next to its picture
    checkpoint 2   <requirements_dir>/review.html   every requirement, each system-level
                                                    one followed by the software-level ones
                                                    refining it, and the glossary terms

Every field of every record is shown. What is new, changed or removed is marked
against the previous approval of the same checkpoint: the latest approval of
other content than the page shows, its files read from git at the commit that
added it. At the first approval nothing is marked.

The page depends only on the files it shows and that commit — no clock, no
machine, a fixed order — so the checkpoint's approval gate renders it again and
compares byte for byte (§ 5 stages 1 and 2, rules 22–24). The agent never writes
it by hand; it renders it, and commits it, before the person reviews.

    python agent/render_review_tool.py --checkpoint 1|2 [--root PRODUCT]
"""

from __future__ import annotations

import argparse
import dataclasses
import html
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.read_archify_diagram_adapter import read_archify_diagrams  # noqa: E402
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
from tools.validate_contract_tool import validate  # noqa: E402

__all__ = ["render", "render_review", "review_page", "review_page_findings"]

APPROVES = {1: "diagrams", 2: "requirements"}
CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"
ELEMENT_FIELDS = ["id", "kind", "label", "from", "to", "wishes"]


def review_page(config: ProductConfig, checkpoint: int) -> Path:
    folder = config.diagrams_dir if checkpoint == 1 else config.requirements_dir
    return folder / "review.html"


def render_review(root: Path, checkpoint: int) -> Path:
    """Write the checkpoint's review page and return its path."""
    config = read_product_config(root)
    page = review_page(config, _checked(checkpoint))
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(render(config, checkpoint), encoding="utf-8")
    return page


def render(config: ProductConfig, checkpoint: int) -> str:
    """The review page's text, from the files as they are and the previous approval."""
    _checked(checkpoint)
    baseline, commit = _baseline(config, checkpoint)
    old: list[dict] | None = None
    if commit is not None:
        with tempfile.TemporaryDirectory() as folder:
            old = _model(_config_at(config, checkpoint, commit, Path(folder)), checkpoint)
    if checkpoint == 1:
        title, intro = "Checkpoint 1 — the diagrams", "Each diagram's picture, then every element."
    else:
        title, intro = (
            "Checkpoint 2 — the requirements",
            (
                "Each system-level requirement, followed by the software-level ones refining it; "
                "then the glossary."
            ),
        )
    if commit is None:
        against = "Nothing is marked: no earlier approval of this checkpoint to compare with."
    else:
        against = (
            f"Marked against the previous approval, {html.escape(baseline)}, "
            f"at commit <code>{commit}</code>."
        )
    sections = _model(config, checkpoint)
    body = "".join(_section(s, old) for s in sections)
    for section in old or []:  # a whole diagram or file removed since the approval
        if section["key"] not in {s["key"] for s in sections}:
            gone = {k: v for k, v in section.items() if k != "picture"}
            body += _section({**gone, "rows": []}, [section], removed=True)
    return PAGE.format(title=title, intro=intro, against=against, body=body)


def review_page_findings(config: ProductConfig, checkpoint: int) -> list[Finding]:
    """The page missing, or different from a fresh render while it awaits approval.

    Once a current approval covers the page, its hashes hold it: a later framework
    version that renders differently does not withdraw an approval."""
    page = review_page(config, checkpoint)
    shown = config.relative(page)
    if not page.is_file():
        return [
            Finding(
                "MISSING_REVIEW_PAGE",
                shown,
                None,
                f"No review page for checkpoint {checkpoint}; render it with "
                f"agent/render_review_tool.py --checkpoint {checkpoint} and commit it, so the "
                "person reviews a page, not the raw files.",
            )
        ]
    if approval_state(config, checkpoint, APPROVES[checkpoint]).status == "approved":
        return []
    if page.read_text(encoding="utf-8") != render(config, checkpoint):
        return [
            Finding(
                "REVIEW_PAGE_OUTDATED",
                shown,
                None,
                f"The review page differs from what the files render now (stale or edited "
                f"by hand); render it again with agent/render_review_tool.py --checkpoint "
                f"{checkpoint} and commit it.",
            )
        ]
    return []


# --- the model: sections of rows, each row a key and its fields -------------------------


def _model(config: ProductConfig, checkpoint: int) -> list[dict]:
    return _diagrams(config) if checkpoint == 1 else _requirements(config)


def _diagrams(config: ProductConfig) -> list[dict]:
    sections = []
    for path, result in read_archify_diagrams(config.diagrams_dir, config.root):
        name = path.name.split(".", 1)[0]
        links = _wish_links(path.with_name(f"{name}.wishes.yaml"))
        rows = []
        for element in (result.diagram or {}).get("elements", []):
            if element["kind"] == "invariant":
                continue
            fields = {k: v for k, v in element.items() if k not in ("line", "source")}
            if element["id"] in links:
                fields["wishes"] = links[element["id"]]
            rows.append({"key": element["id"], "fields": fields})
        rows += [
            {"key": f"problem {i + 1}", "fields": {"problem": f"{p.rule}: {p.message}"}}
            for i, p in enumerate(result.problems)
        ]
        picture = path.with_suffix(".html")
        sections.append(
            {
                "key": path.name,
                "heading": path.name,
                "picture": picture.name if picture.is_file() else None,
                "columns": ELEMENT_FIELDS,
                "rows": rows,
            }
        )
        invariants = _invariants(path.with_name(f"{name}.invariants.yaml"))
        for row in invariants:
            if row["key"] in links:
                row["fields"] = {**row["fields"], "wishes": links[row["key"]]}
        if invariants:
            sections.append(
                {
                    "key": f"{name}.invariants.yaml",
                    "heading": f"{name}.invariants.yaml",
                    "columns": _columns("invariants", invariants, "invariants"),
                    "rows": invariants,
                }
            )
    return sections


def _requirements(config: ProductConfig) -> list[dict]:
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
    sections = [
        {
            "key": "requirements",
            "heading": "Requirements",
            "columns": _columns("requirement", ordered),
            "rows": ordered,
        }
    ]
    glossary = config.glossary_file
    if glossary.is_file():
        shown = config.relative(glossary)
        terms = [_block_row(shown, b) for b in read_yaml_blocks(glossary, "glossary_term")]
        sections.append(
            {
                "key": "glossary",
                "heading": config.relative(glossary),
                "columns": _columns("glossary_term", terms),
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


def _wish_links(file: Path) -> dict[str, list]:
    data = _yaml(file)
    if not isinstance(data, dict) or validate(data, "diagram_wishes"):
        return {}
    return data["links"]


def _invariants(file: Path) -> list[dict]:
    data = _yaml(file)
    if not isinstance(data, dict) or not isinstance(data.get("invariants"), list):
        return []
    return [
        {"key": str(entry.get("id", f"entry {i + 1}")), "fields": entry}
        for i, entry in enumerate(data["invariants"])
        if isinstance(entry, dict)
    ]


def _yaml(file: Path) -> Any:
    if not file.is_file():
        return None
    try:
        return read_yaml_file(file)
    except YamlReadError:
        return None


def _columns(contract: str, rows: list[dict], nested: str | None = None) -> list[str]:
    """The contract's fields in its own order, then any other field a row holds."""
    schema = json.loads((CONTRACTS / f"{contract}_contract.v1.schema.json").read_text())
    properties = schema["properties"]
    if nested:
        properties = properties[nested]["items"]["properties"]
    present = [k for row in rows for k in row["fields"]]
    return [k for k in properties if k in present] + sorted(set(present) - set(properties))


# --- the baseline: the previous approval's files, from git -------------------------------


def _baseline(config: ProductConfig, checkpoint: int) -> tuple[str, str | None]:
    """The previous approval and the commit that added it: the latest approval of
    other content than the page shows. None when there is none, or it is not committed."""
    approves = APPROVES[checkpoint]
    shown = {
        config.relative(f): sha256(f)
        for f in subject_files(config, approves)
        if f.suffix != ".html"
    }
    folder = config.approvals_dir
    pattern = f"*-checkpoint-{checkpoint}-{approves}.yaml"
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
        return config.relative(path), _added_in(config.root, path)
    return "", None


def _added_in(root: Path, file: Path) -> str | None:
    if not in_git(root):
        return None
    commits = _git(root, "log", "--diff-filter=A", "--format=%H", "--", str(file)).split()
    return commits[-1] if commits else None


def _config_at(config: ProductConfig, checkpoint: int, commit: str, folder: Path) -> ProductConfig:
    """The configuration over a copy of the files the page shows, as they were at a commit
    (the pictures left out: the page only links them)."""
    if checkpoint == 1:
        shown = [config.diagrams_dir]
    else:
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


def _section(section: dict, old: list[dict] | None, removed: bool = False) -> str:
    before = next((s for s in old or [] if s["key"] == section["key"]), None)
    previous = {r["key"]: r["fields"] for r in (before or {}).get("rows", [])}
    columns = section["columns"]
    if before is not None:
        columns = columns + [c for c in before["columns"] if c not in columns]
    heading = html.escape(section["heading"])
    if removed:
        heading += ' <span class="mark removed">removed</span>'
    elif old is not None and before is None:
        heading += ' <span class="mark new">new</span>'
    parts = [f"<section>\n<h2>{heading}</h2>\n"]
    if section.get("picture"):
        name = html.escape(section["picture"])
        parts.append(
            f'<p><a href="{name}">Open the picture</a></p>\n'
            f'<iframe src="{name}" title="{name}" loading="lazy"></iframe>\n'
        )
    elif "picture" in section:
        parts.append("<p>No picture yet.</p>\n")
    head = "".join(f"<th>{html.escape(c)}</th>" for c in ["change", *columns])
    parts.append(f"<table>\n<thead><tr>{head}</tr></thead>\n<tbody>\n")
    keys = set()
    for row in section["rows"]:
        keys.add(row["key"])
        was = previous.get(row["key"])
        if old is None:
            mark = ""
        elif was is None:
            mark = "new"
        else:
            mark = "changed" if was != row["fields"] else ""
        parts.append(_row(mark, columns, row["fields"], was if mark == "changed" else None))
    for key, fields in previous.items():
        if key not in keys:
            parts.append(_row("removed", columns, fields, None))
    parts.append("</tbody>\n</table>\n</section>\n")
    return "".join(parts)


def _row(mark: str, columns: list[str], fields: dict, was: dict | None) -> str:
    cells = [f'<td class="mark {mark}">{mark}</td>' if mark else "<td></td>"]
    for column in columns:
        differs = was is not None and was.get(column) != fields.get(column)
        cls = ' class="differs"' if differs else ""
        cells.append(f"<td{cls}>{_value(fields.get(column))}</td>")
    cls = f' class="{mark}"' if mark else ""
    return f"<tr{cls}>{''.join(cells)}</tr>\n"


def _value(value: Any) -> str:
    """A field on the page: a list one item per line, a mapping as key: value pairs."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "<br>\n".join(_value(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(f"<b>{html.escape(str(k))}</b>: {_value(v)}" for k, v in value.items())
    return html.escape(str(value))


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1.5rem; color: #1b1b1b; background: #fff; }}
table {{ border-collapse: collapse; margin: 0.5rem 0 1.5rem; font-size: 0.9rem; }}
th, td {{ border: 1px solid #c8c8c8; padding: 0.3rem 0.5rem; text-align: left;
  vertical-align: top; }}
th {{ background: #f0f0f0; }}
section {{ overflow-x: auto; }}
iframe {{ width: 100%; height: 32rem; border: 1px solid #c8c8c8; }}
.mark {{ font-weight: 600; }}
.new {{ background: #e3f6e3; }}
.changed {{ background: #fff4d6; }}
.removed {{ background: #fbe3e3; text-decoration: line-through; }}
.differs {{ outline: 2px solid #d29b00; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p>{intro} Rendered by the framework's render_review_tool from the committed files;
never edited by hand.</p>
<p>{against}</p>
{body}</body>
</html>
"""


def _checked(checkpoint: int) -> int:
    if checkpoint not in APPROVES:
        raise ValueError(f"checkpoint {checkpoint} has no review page: only 1 and 2 have one")
    return checkpoint


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--checkpoint", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        path = render_review(args.root, args.checkpoint)
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
