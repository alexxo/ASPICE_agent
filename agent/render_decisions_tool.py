"""Render the decisions page, ask the person a decision, record their answer.

<decisions_dir>/index.html lists every decision record (decision.v1) that says
who decides, in the one layout (tools/render_page_tool.py), nothing folded:

- Waiting for you — the person's, proposed: a critical requirement depends on
  it (criticality high, or kind security). Its card: Question, Why you, Before
  (what the record it supersedes chose), Options, Select, Proposed, Answer.
- Answered by you — the person's, accepted: the same card with the answer.
- Decided by the agent — no critical requirement depends on it, so the person
  was not asked: what was chosen, what was considered, why it is not critical,
  where it is in the work, and a "Change this" link that opens a change
  request with the decision filled in.
- Recorded with the architecture — the records without decided_by, which
  checkpoint 3 approves.

A superseded record is not a card of its own: its choice is the Before of the
record that supersedes it, so nothing is asked twice. The page depends only on
the records, the requirements and the product's repository, so
verify_decision_records_gate renders it again and compares.

    python agent/render_decisions_tool.py [--root PRODUCT] [--no-open]
        writes the page and opens it in the browser
    python agent/render_decisions_tool.py --ask ADR-NNNN [--root PRODUCT]
        prints the person's decision as the card, for the terminal
    python agent/render_decisions_tool.py --ask ADR-NNNN --answer TEXT --by NAME
        records the answer (Y, or an option's number): status accepted, the
        choice, who answered and when; then renders the page again
"""

from __future__ import annotations

import argparse
import html
import sys
import urllib.parse
from datetime import date
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from agent.ask_person_tool import check, reply  # noqa: E402
from agent.ask_person_tool import render as ask
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_host_tool import HostError, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig, read_product_config  # noqa: E402
from tools.read_requirements_tool import critical, read_requirements  # noqa: E402
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.render_page_tool import card, open_page, page, section  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

__all__ = [
    "choice_of",
    "decisions_page",
    "decisions_page_findings",
    "read_decisions",
    "record_answer",
    "render",
    "render_decisions",
]

LEAD = (
    "Every decision about what the product does: the ones waiting for you, the ones you "
    "answered, and the ones the agent made alone because no critical requirement depends on "
    "them. Rendered by the framework's render_decisions_tool from the decision records; never "
    "edited by hand."
)


def decisions_page(config: ProductConfig) -> Path:
    return config.decisions_dir / "index.html"


def read_decisions(config: ProductConfig) -> dict[str, tuple[Path, dict]]:
    """Every valid decision record, by ID, with its file."""
    folder = config.decisions_dir
    found: dict[str, tuple[Path, dict]] = {}
    for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        blocks = read_yaml_blocks(path, "decision")
        if len(blocks) == 1 and not blocks[0].error and not validate(blocks[0].data, "decision"):
            found.setdefault(blocks[0].data["id"], (path, blocks[0].data))
    return found


def render_decisions(root: Path) -> Path:
    """Write the decisions page and return its path."""
    config = read_product_config(root)
    target = decisions_page(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(config), encoding="utf-8")
    return target


def render(config: ProductConfig) -> str:
    records = {key: data for key, (_, data) in read_decisions(config).items()}
    requirements = {r.text("uid"): r.data for r in read_requirements(config) if r.text("uid")}
    link = _change_link(config)
    live = [d for d in records.values() if d["status"] != "superseded"]
    waiting = [d for d in live if d.get("decided_by") == "person" and d["status"] == "proposed"]
    answered = [d for d in live if d.get("decided_by") == "person" and d["status"] == "accepted"]
    agent = [d for d in live if d.get("decided_by") == "agent"]
    architecture = [d for d in live if "decided_by" not in d]
    body = section(
        f"Waiting for you ({len(waiting)})",
        "".join(_person_card(d, records, requirements) for d in waiting) or "<p>Nothing.</p>\n",
    )
    body += section(
        f"Answered by you ({len(answered)})",
        "".join(_person_card(d, records, requirements) for d in answered) or "<p>Nothing.</p>\n",
    )
    body += section(
        f"Decided by the agent ({len(agent)})",
        "".join(_agent_card(d, records, requirements, link) for d in agent) or "<p>Nothing.</p>\n",
        "No critical requirement depends on these, so you were not asked. Each says what was "
        "chosen and why; the reviewer agent checks each one. Change any of them with its link.",
    )
    if architecture:
        body += section(
            f"Recorded with the architecture ({len(architecture)})",
            "".join(_architecture_card(d, records) for d in architecture),
            "Approved with the stack at checkpoint 3.",
        )
    summary = (
        f"<b>{len(waiting)} wait{'s' if len(waiting) == 1 else ''} for you.</b> "
        f"{len(answered)} answered by you, none asked again. "
        f"{len(agent)} decided by the agent; you can change any of them."
    )
    return page("Decisions", LEAD, summary, body)


def choice_of(record: dict, records: dict[str, dict]) -> dict:
    """The person's decision as a choice.v1, for the terminal and the code host."""
    names = [o["name"] for o in record["options"]]
    choice = {
        "question": record["question"],
        "why_you": record["why_you"],
        "options": _options(record),
        "select": names,
    }
    before = _before(record, records)
    if before:
        choice["before"] = before
    if record["status"] == "proposed" and record["choice"] in names:
        choice["proposal"] = {
            "choice": names.index(record["choice"]) + 1,
            "why": record["proposed_because"],
        }
    return check(choice)


def record_answer(config: ProductConfig, ident: str, text: str, by: str, today: date) -> dict:
    """Record the person's answer to their proposed decision: status accepted, the
    option chosen, who answered and when. ValueError when it is no such decision,
    or the answer selects no option."""
    found = read_decisions(config).get(ident)
    if found is None:
        raise ValueError(f"{ident} is no decision record of the product")
    path, record = found
    if record.get("decided_by") != "person" or record["status"] != "proposed":
        raise ValueError(f"{ident} waits for no answer: it is not the person's, or not proposed")
    records = {key: data for key, (_, data) in read_decisions(config).items()}
    selected = reply(choice_of(record, records), text)
    if selected is None:
        raise ValueError(f"'{text}' selects no option of {ident}")
    updated = {
        **record,
        "status": "accepted",
        "date": today.isoformat(),
        "choice": record["options"][selected - 1]["name"],
        "answered_by": by,
    }
    updated.pop("proposed_because", None)
    source = path.read_text(encoding="utf-8")
    block = read_yaml_blocks(path, "decision")[0]
    lines = source.splitlines(keepends=True)
    start = block.line - 1  # the first line of the block's content
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("```"))
    dumped = yaml.safe_dump(updated, sort_keys=False, allow_unicode=True, width=1000)
    path.write_text("".join(lines[:start]) + dumped + "".join(lines[end:]), encoding="utf-8")
    return updated


def decisions_page_findings(config: ProductConfig) -> list[Finding]:
    """The page missing, or not what the records render now, once a record says
    who decides."""
    records = read_decisions(config)
    if not any("decided_by" in data for _, data in records.values()):
        return []
    target = decisions_page(config)
    shown = config.relative(target)
    if not target.is_file():
        return [
            Finding(
                "MISSING_DECISIONS_PAGE",
                shown,
                None,
                "No decisions page; render it with agent/render_decisions_tool.py and commit "
                "it, so the person sees every decision in one place.",
            )
        ]
    if target.read_text(encoding="utf-8") != render(config):
        return [
            Finding(
                "DECISIONS_PAGE_OUTDATED",
                shown,
                None,
                "The decisions page is not what the records render now; render it again with "
                "agent/render_decisions_tool.py and commit it.",
            )
        ]
    return []


# --- the cards ---------------------------------------------------------------------------


def _person_card(record: dict, records: dict[str, dict], requirements: dict) -> str:
    names = [o["name"] for o in record["options"]]
    lines = {
        "Question": html.escape(record["question"]),
        "Why you": html.escape(record["why_you"]),
    }
    before = _before(record, records)
    if before:
        lines["Before"] = html.escape(before)
    lines["Options"] = html.escape(_options(record))
    lines["Select"] = [html.escape(n) for n in names]
    number = names.index(record["choice"]) + 1 if record["choice"] in names else None
    if record["status"] == "proposed":
        if number:
            lines["Proposed"] = (
                f"{number}. {html.escape(record['choice'])}: "
                f"{html.escape(record['proposed_because'])}"
            )
        answers = " ".join(
            f"<code>{a}</code>" for a in (["Y"] if number else []) + list(range(1, len(names) + 1))
        )
        lines["Answer"] = f"{answers} in the terminal"
        kind = "open"
    else:
        lines["Answer"] = (
            f"{number}. {html.escape(record['choice'])}, on {record['date']}, "
            f"by {html.escape(record.get('answered_by', ''))}"
        )
        kind = "answered"
    return card(kind, lines, meta=_meta(record, requirements), anchor=record["id"])


def _agent_card(record: dict, records: dict, requirements: dict, link: str | None) -> str:
    lines = {}
    before = _before(record, records)
    if before:
        lines["Before"] = html.escape(before)
    lines["Considered"] = html.escape(" or ".join(o["name"] for o in record["options"]))
    lines["Chosen"] = f"{html.escape(record['choice'])}: {html.escape(record['consequences'])}"
    lines["Not critical"] = html.escape(record.get("not_critical", ""))
    lines["In the work"] = (
        f'<span class="meta">{html.escape(" · ".join(record.get("where", [])))}</span>'
    )
    action = ""
    if link:
        query = urllib.parse.urlencode(
            {
                "labels": "change-request",
                "title": f"Change {record['id']}: {record['title']}",
                "body": _change_body(record),
            }
        )
        action = f'<a href="{html.escape(link + "?" + query)}">Change this</a>'
    return card(
        "agent",
        lines,
        title=html.escape(record["title"]),
        action=action,
        meta=_meta(record, requirements),
        anchor=record["id"],
    )


def _architecture_card(record: dict, records: dict) -> str:
    lines = {}
    before = _before(record, records)
    if before:
        lines["Before"] = html.escape(before)
    lines["Considered"] = html.escape(" or ".join(o["name"] for o in record["options"]))
    lines["Chosen"] = f"{html.escape(record['choice'])}: {html.escape(record['consequences'])}"
    kind = "answered" if record["status"] == "accepted" else "open"
    return card(
        kind, lines, title=html.escape(record["title"]), meta=record["id"], anchor=record["id"]
    )


def _options(record: dict) -> str:
    """The options in sentences: what speaks for each, and against."""
    return " Or ".join(
        f"{o['name']}: {'; '.join(o['pros'])}; but {'; '.join(o['cons'])}."
        for o in record["options"]
    )


def _before(record: dict, records: dict[str, dict]) -> str:
    """What the superseded record chose, and who: what the person answered before."""
    old = records.get(record.get("supersedes", ""))
    if old is None:
        return ""
    if old.get("decided_by") == "person":
        return f"On {old['date']} you answered: {old['choice']}."
    if old.get("decided_by") == "agent":
        return f"On {old['date']} the agent decided: {old['choice']}."
    return f"On {old['date']}, with the architecture: {old['choice']}."


def _meta(record: dict, requirements: dict) -> str:
    parts = []
    for uid in record.get("requirements", []):
        data = requirements.get(uid, {})
        rating = "critical" if critical(data) else data.get("criticality", "unknown")
        parts.append(f"{uid} {html.escape(str(rating))}")
    if "change_request" in record:
        parts.append(f"#{record['change_request']}")
    parts.append(record["id"])
    return " · ".join(parts)


def _change_body(record: dict) -> str:
    return (
        "```yaml change_request\n"
        f"what: Change {record['id']}, decided by the agent: {record['title']}\n"
        "initiator: \n"
        "reason: \n"
        "status: requested\n"
        "```\n"
    )


def _change_link(config: ProductConfig) -> str | None:
    try:
        return f"https://github.com/{repository(config.root)}/issues/new"
    except HostError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--ask", metavar="ADR-NNNN")
    parser.add_argument("--answer")
    parser.add_argument("--by")
    args = parser.parse_args(argv)
    config = read_product_config(args.root)
    if args.ask and args.answer is None:
        records = {key: data for key, (_, data) in read_decisions(config).items()}
        record = records.get(args.ask)
        if record is None or record.get("decided_by") != "person":
            print(f"{args.ask} is no decision of the person's", file=sys.stderr)
            return 2
        try:
            print(ask(choice_of(record, records)))
        except ValueError as err:
            print(str(err), file=sys.stderr)
            return 2
        print(f"Page: {config.relative(decisions_page(config))}")
        return 0
    if args.ask:
        if not args.by:
            print("--answer needs --by NAME: who answered", file=sys.stderr)
            return 2
        try:
            record_answer(config, args.ask, args.answer, args.by, date.today())
        except ValueError as err:
            print(str(err), file=sys.stderr)
            return 1
    target = render_decisions(args.root)
    print(target if args.no_open else open_page(target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
