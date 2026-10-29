"""The one layout of every page and every decision a person reads.

A page is a title, one line of lead, one summary line, then sections; a
decision is a card of labelled lines, always the same ones in the same order:
Question, Why you, Before, Options, Select, Proposed, Answer — those that apply.
Nothing is folded: every line of every card, and every row of every table, is
on the page (§ 5, One layout for the person). The same card prints as text in
the terminal and as Markdown on the code host, so the person meets one pattern
wherever they are asked.

Every tool that writes a page a person reads (the diagrams and requirements
review pages, the decisions page) builds it here; a framework test fails on a
page written any other way.

    from tools.render_page_tool import card, page, section
"""

from __future__ import annotations

import html
import os
import webbrowser
from pathlib import Path

__all__ = ["STYLE", "card", "card_markdown", "card_text", "open_page", "page", "section"]

# The card's lines, in their order; a card shows the ones it has.
LINES = ["Question", "Why you", "Before", "Options", "Select", "Proposed", "Answer"]

STYLE = """\
body { font: 14px system-ui, sans-serif; margin: 1.5rem; color: #111; background: #fff; }
h1 { margin-bottom: 0.2rem; }
h2 { margin-top: 2rem; border-bottom: 1px solid #ccc; padding-bottom: 0.2rem; }
.lead { color: #444; margin-top: 0; }
.summary { background: #fffbe6; border: 1px solid #e6d58a; padding: 0.5rem 0.75rem; }
section { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; margin: 0.5rem 0 1.5rem; }
th, td { border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left;
  vertical-align: top; }
th { background: #eee; position: sticky; top: 0; }
.card { border: 1px solid #ccc; border-left: 5px solid; margin: 0.8rem 0;
  padding: 0.6rem 0.8rem; max-width: 60rem; }
.card.open { border-left-color: #1f6feb; background: #f5f9ff; }
.card.answered { border-left-color: #070; }
.card.agent { border-left-color: #888; }
.line { display: grid; grid-template-columns: 6.5rem 1fr; gap: 0.6rem; margin: 0.25rem 0; }
.label { font-weight: 600; color: #555; }
.why { color: #b00; font-weight: 600; }
.before { color: #05631d; }
.proposed { font-weight: 600; }
.answered .answer { color: #05631d; font-weight: 600; }
.card ol { margin: 0; padding-left: 1.2rem; }
.title { display: grid; grid-template-columns: 1fr auto; gap: 1rem; margin-bottom: 0.3rem; }
.meta { color: #666; font-size: 12px; font-family: ui-monospace, monospace; }
.example { color: #555; font-family: ui-monospace, monospace; margin-left: 0.5rem; }
.conflict { color: #b00; font-weight: 600; }
i { color: #036; }
ins { background: #d7f5dd; color: #05631d; }
del { background: #fde0e0; color: #a40000; }
"""


def page(title: str, lead: str, summary: str, body: str, style: str = "") -> str:
    """The whole page. lead, summary and body are HTML; title is text."""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>\n{STYLE}{style}</style>\n"
        f"</head>\n<body>\n<h1>{html.escape(title)}</h1>\n"
        f'<p class="lead">{lead}</p>\n<p class="summary">{summary}</p>\n{body}</body>\n</html>\n'
    )


def section(heading: str, body: str, lead: str = "") -> str:
    """One section: its heading (text), a lead (HTML) and its body (HTML)."""
    intro = f'<p class="lead">{lead}</p>\n' if lead else ""
    return f"<section>\n<h2>{html.escape(heading)}</h2>\n{intro}{body}</section>\n"


def card(
    kind: str,
    lines: dict[str, str],
    *,
    title: str = "",
    action: str = "",
    meta: str = "",
    anchor: str = "",
) -> str:
    """One card: open (waits for the person), answered (by the person), or agent
    (decided by the agent). lines maps a label to its HTML, shown in the order of
    LINES, then any other label in the order given; Select may be a list of
    labels, shown numbered. title and action (HTML) head an agent's card."""
    ident = f' id="{html.escape(anchor)}"' if anchor else ""
    parts = [f'<div class="card {kind}"{ident}>']
    if title or action:
        parts.append(f'<div class="title"><b>{title}</b><span>{action}</span></div>')
    order = [label for label in LINES if label in lines] + [
        label for label in lines if label not in LINES
    ]
    for label in order:
        value = lines[label]
        if isinstance(value, list):
            value = "<ol>" + "".join(f"<li>{item}</li>" for item in value) + "</ol>"
        cls = {"Why you": "why", "Before": "before", "Proposed": "proposed", "Answer": "answer"}
        shown = (
            f'<span class="{cls[label]}">{value}</span>'
            if label in cls
            else f"<span>{value}</span>"
        )
        parts.append(f'<div class="line"><span class="label">{label}</span>{shown}</div>')
    if meta:
        parts.append(f'<div class="meta">{meta}</div>')
    parts.append("</div>\n")
    return "\n".join(parts)


def card_text(lines: dict[str, object], answer: str = "") -> str:
    """The card as terminal text: one labelled line each, in the order of LINES;
    Select numbered on one line; the prompt for the answer last."""
    out = []
    for label in [label for label in LINES if label in lines]:
        value = lines[label]
        if label == "Select":
            value = ", ".join(f"{i}. {item}" for i, item in enumerate(value, 1))
            out.append(f"Select your option: {value}")
            continue
        if label == "Answer":
            continue
        out.append(f"{label}: {value}")
    if answer:
        out.append(f"Your answer [{answer}]:")
    return "\n".join(out)


def card_markdown(lines: dict[str, object]) -> str:
    """The card in Markdown for the code host: one bold label each, Select as a box
    per option, which the person ticks."""
    out = []
    for label in [label for label in LINES if label in lines]:
        value = lines[label]
        if label == "Answer":
            continue
        if label == "Select":
            boxes = "\n".join(f"- [ ] {i}. {item}" for i, item in enumerate(value, 1))
            out.append(f"**Select your option:**\n{boxes}")
            continue
        out.append(f"**{label}:** {value}")
    return "\n\n".join(out)


def open_page(path: Path) -> str:
    """Open a page written for the person in the browser of this computer, and say
    so; never in CI or a test run, where nobody looks."""
    if os.environ.get("CI") or os.environ.get("PYTEST_CURRENT_TEST"):
        return str(path)
    opened = webbrowser.open(Path(path).resolve().as_uri())
    return f"{path} (opened in the browser)" if opened else f"{path} (open it in the browser)"
