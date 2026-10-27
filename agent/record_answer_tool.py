"""Record the check for unclear criteria, and the person's answer to each question.

Before checkpoint 2 a session that sees only the requirements, the glossary and
the approved diagrams (agent/clarify_criteria_prompt.md) flags each acceptance
criterion, or glossary term, whose readings would need different tests. Its
questions and the person's answers live in <requirements_dir>/questions.yaml
(question.v1), with the SHA-256 of every criterion and term the check has seen:
one left unchanged is never asked about again, nor one unchanged since the
latest approval of checkpoint 2. Questions are numbered in the review page's
order, top to bottom, so the person answers them as the page shows them. One
question may settle several criteria and terms (`also`): one rule, one
question. A criterion is checked again once after its rewrite: one settled at
two texts since the latest approval — the check and that recheck — counts as
checked when it is rewritten again, so the rounds end.

    python agent/record_answer_tool.py --unchecked [--root PRODUCT]
        prints the criteria and terms the check has not seen yet; one rewritten
        to settle a question names it, so only the rewrite's wording is checked
    python agent/record_answer_tool.py --questions FILE [--root PRODUCT]
        records the session's questions (a YAML list, without id and asked)
        and every criterion and term as checked
    python agent/record_answer_tool.py --question Q1 --choice N --approver NAME \\
        --role ROLE [--again] [--root PRODUCT]
        records the person's answer: a reading's number, or the one after the
        last for 'neither: the requirement goes back to be rewritten'; --again
        changes an answer whose criterion is not rewritten yet
    python agent/record_answer_tool.py --ask Q1 [--root PRODUCT]
        prints the question as a choice.v1, for agent/ask_person_tool.py --file -
    python agent/record_answer_tool.py --summary [--root PRODUCT]
        prints, as a short story per answer, what the answers not yet written
        into the criteria decide, the risky ones first, each with why

An unanswered question whose criterion or term changed since it was asked no
longer counts: the changed text is unchecked, and is checked again (§ 5 stages 1
and 2, rule 27).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig, read_product_config  # noqa: E402
from tools.read_requirements_tool import read_requirements  # noqa: E402
from tools.read_yaml_blocks_tool import (  # noqa: E402
    YamlReadError,
    read_yaml_blocks,
    read_yaml_file,
)
from tools.validate_contract_tool import validate  # noqa: E402

__all__ = [
    "checked",
    "choice",
    "items",
    "label",
    "neither",
    "open_questions",
    "pending",
    "place",
    "places",
    "question_findings",
    "questions_file",
    "read_questions",
    "record_answer",
    "record_check",
    "summary",
    "unchecked",
]


def questions_file(config: ProductConfig) -> Path:
    return config.requirements_dir / "questions.yaml"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def place(about: dict) -> tuple:
    """Where a question points: (requirement, criterion) or ('term', term)."""
    if "term" in about:
        return ("term", about["term"])
    return (about["requirement"], about["criterion"])


def places(question: dict) -> list[tuple]:
    """Every place a question settles: its own, then those of `also`."""
    return [place(a) for a in [question["about"], *question.get("also", [])]]


def label(about: dict) -> str:
    if "term" in about:
        return f"term {about['term']}"
    return f"{about['requirement']} criterion {about['criterion']}"


def items(config: ProductConfig) -> dict[tuple, str]:
    """Every acceptance criterion and glossary term, by its place, as the SHA-256 of
    its text."""
    found: dict[tuple, str] = {}
    for req in read_requirements(config):
        uid = req.text("uid")
        criteria = req.data.get("acceptance_criteria") if uid else None
        for i, criterion in enumerate(criteria if isinstance(criteria, list) else [], 1):
            text = json.dumps(criterion, sort_keys=True, ensure_ascii=False)
            found[(uid, i)] = _sha(f"{uid} {i}\n{text}")
    glossary = config.glossary_file
    for block in read_yaml_blocks(glossary, "glossary_term") if glossary.is_file() else []:
        if isinstance(block.data, dict) and block.data.get("term"):
            text = json.dumps(block.data, sort_keys=True, ensure_ascii=False)
            found[("term", str(block.data["term"]))] = _sha(f"term\n{text}")
    return found


def read_questions(config: ProductConfig) -> dict:
    """The questions file, or an empty one; a file that does not read raises ValueError."""
    path = questions_file(config)
    if not path.is_file():
        return {"checked": [], "questions": []}
    try:
        data = read_yaml_file(path)
    except YamlReadError as err:
        raise ValueError(f"{config.relative(path)} does not read: {err}") from err
    violations = validate(data, "question")
    if violations:
        first = violations[0]
        raise ValueError(
            f"{config.relative(path)} is not a valid question.v1 at "
            f"'{first.path or 'the file'}': {first.message}"
        )
    return data


def _write(config: ProductConfig, data: dict) -> Path:
    violations = validate(data, "question")
    if violations:
        first = violations[0]
        raise ValueError(f"not valid at '{first.path or 'the file'}': {first.message}")
    path = questions_file(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def neither(question: dict) -> int:
    """The number of 'neither: the requirement goes back to be rewritten'."""
    return len(question["readings"]) + 1


def open_questions(config: ProductConfig, data: dict | None = None) -> list[dict]:
    """The questions still to answer: no answer, and their text unchanged since asked."""
    data = read_questions(config) if data is None else data
    now = items(config)
    return [
        q
        for q in data["questions"]
        if "answer" not in q and now.get(place(q["about"])) == q["asked"]
    ]


def pending(config: ProductConfig, data: dict | None = None) -> list[dict]:
    """The answered questions whose criterion or term is not rewritten yet."""
    data = read_questions(config) if data is None else data
    now = items(config)
    return [
        q for q in data["questions"] if "answer" in q and now.get(place(q["about"])) == q["asked"]
    ]


def summary(config: ProductConfig) -> list[str]:
    """What the pending answers decide, told as a short story: the question, the
    situation the person is in, what the product will do and what that means for
    them, the requirement last, as a reference. The risky ones first, each with
    why — a requirement of high criticality or about security, a term every
    requirement using it follows, a reading that contradicts another requirement,
    a proposal taken from common practice rather than anything approved."""
    requirements = {r.text("uid"): r.data for r in read_requirements(config) if r.text("uid")}
    risky, rest = [], []
    for q in pending(config):
        about = q["about"]
        choice = q["answer"]["choice"]
        lines = [f"{q['id']} — {q['question']}"]
        if q.get("situation"):
            lines.append(f"When {q['situation']}:")
        why = []
        if choice == neither(q):
            lines.append("neither reading — the requirement goes back to be rewritten")
        else:
            reading = q["readings"][choice - 1]
            lines.append(f"the product will — {reading['reading']} (e.g. {reading['example']})")
            if reading.get("means"):
                lines.append(f"For you: {reading['means']}")
            if "term" in about:
                term = about["term"]
                using = [uid for uid, data in requirements.items() if f"_{term}_" in str(data)]
                why.append(f"it changes every requirement using the term ({len(using)})")
            else:
                data = requirements.get(about["requirement"], {})
                if data.get("criticality") == "high":
                    why.append("a requirement of high criticality")
                if data.get("kind") == "security":
                    why.append("a security requirement")
            if reading.get("conflicts"):
                why.append(f"it contradicts {reading['conflicts']}")
            proposal = q.get("proposal")
            taken = isinstance(proposal, dict) and proposal["choice"] == choice
            if taken and str(proposal["source"]).startswith("convention"):
                why.append("decided by common practice, not by anything you approved")
        if why:
            lines.append(f"Risky: {'; '.join(why)}.")
        lines.append(f"About: {_reference(q, requirements)}")
        text = "\n    ".join(lines)
        (risky if why else rest).append(f"⚠ {text}" if why else text)
    return risky + rest


def _reference(question: dict, requirements: dict[str, dict]) -> str:
    """The requirement a question is about, by its statement, then its ID."""
    about = question["about"]
    if "term" in about:
        shown = f"the glossary term {about['term']}"
    else:
        statement = str(requirements.get(about["requirement"], {}).get("statement", "")).strip()
        statement = re.sub(r"_([^_\s][^_]*)_", r"\1", statement)  # a term's mark, not its word
        shown = f'"{statement}" ' if statement else ""
        shown += f"({about['requirement']}, criterion {about['criterion']})"
    more = question.get("also") or []
    return shown + (f", and {len(more)} more" if more else "")


def choice(question: dict) -> dict:
    """The question as the person is asked it (choice.v1): the options explained —
    the situation, each reading with what it means for them — and selected by
    their labels, the last one 'neither'; the proposal with its source."""
    readings = []
    for r in question["readings"]:
        means = f" ({r['means']})" if r.get("means") else ""
        readings.append(f"{r['reading']}{means}")
    situation = f"When {question['situation']}: " if question.get("situation") else ""
    asked = {
        "question": question["question"].rstrip(" ?.") + "?",
        "options": f"{situation}{'; or '.join(readings)}. Or neither, and the requirement "
        "goes back to be rewritten.",
        "select": [r.get("label") or r["reading"] for r in question["readings"]]
        + ["neither: rewrite the requirement"],
    }
    proposal = question.get("proposal")
    if isinstance(proposal, dict):
        asked["proposal"] = {"choice": proposal["choice"], "why": proposal["source"]}
    return asked


def record_check(root: Path, session_file: Path) -> Path:
    """Record the session's questions and every criterion and term as checked."""
    config = read_product_config(root)
    data = read_questions(config)
    try:
        asked = read_yaml_file(session_file)
    except YamlReadError as err:
        raise ValueError(f"{session_file} does not read: {err}") from err
    if asked is None:
        asked = []
    if not isinstance(asked, list):
        raise ValueError(f"{session_file} must hold a YAML list of questions")
    now = items(config)
    number = max((int(q["id"][1:]) for q in data["questions"]), default=0)
    for entry in asked:
        if not isinstance(entry, dict) or not isinstance(entry.get("about"), dict):
            raise ValueError(f"every question in {session_file} needs an 'about'")
    from agent.render_review_tool import page_order

    order = {key: i for i, key in enumerate(page_order(config))}
    for entry in sorted(asked, key=lambda e: _on_page(order, place(e["about"]))):
        for about in [entry["about"], *(entry.get("also") or [])]:
            if not isinstance(about, dict) or place(about) not in now:
                raise ValueError(f"{label(about)}: no such criterion or glossary term")
        sha = now[place(entry["about"])]
        number += 1
        data["questions"].append({"id": f"Q{number}", **entry, "asked": sha})
        proposal = entry.get("proposal")
        if isinstance(proposal, dict) and not 1 <= proposal.get("choice", 0) <= len(
            entry.get("readings") or []
        ):
            raise ValueError(f"Q{number}: the proposal is not one of its readings")
    data["checked"] = sorted(set(data["checked"]) | set(now.values()))
    return _write(config, data)


def record_answer(
    root: Path, question: str, choice: int, approver: str, role: str, again: bool = False
) -> Path:
    """Record the person's answer to one open question, or, again, change the answer
    to one whose criterion is not rewritten yet."""
    config = read_product_config(root)
    data = read_questions(config)
    found = next((q for q in data["questions"] if q["id"] == question), None)
    if found is None:
        raise ValueError(f"no question {question}")
    if again:
        if found not in pending(config, data):
            raise ValueError(f"{question} has no answer to change: open, or rewritten since")
    elif found not in open_questions(config, data):
        raise ValueError(f"{question} is not open: answered, or its text changed since")
    if not 1 <= choice <= neither(found):
        raise ValueError(f"{question}: choose 1 to {neither(found)}")
    proposal = found["proposal"]
    taken = (
        "none"
        if proposal == "none"
        else ("accepted" if proposal["choice"] == choice else "changed")
    )
    found["answer"] = {
        "choice": choice,
        "approver": {"name": approver, "role": role},
        "proposal": taken,
    }
    return _write(config, data)


def question_findings(config: ProductConfig, unanswered: bool = True) -> list[Finding]:
    """A criterion or term not checked yet, a question not answered (unless
    unanswered is False: the person answers at the checkpoint, not the agent), and
    one answered 'neither' whose requirement is not rewritten yet."""
    shown = config.relative(questions_file(config))
    try:
        data = read_questions(config)
    except ValueError as err:
        return [Finding("QUESTION_UNANSWERED", shown, None, f"{err}; no answer can be read.")]
    now = items(config)
    findings = []
    seen = checked(config, data)
    missing = [k for k, sha in now.items() if sha not in seen]
    if missing:
        names = ", ".join(label(_about(k)) for k in missing[:8])
        more = f" and {len(missing) - 8} more" if len(missing) > 8 else ""
        findings.append(
            Finding(
                "CRITERIA_NOT_CHECKED",
                shown,
                None,
                f"Not checked for unclear readings: {names}{more}. Run the check "
                "(agent/clarify_criteria_prompt.md) and record it with "
                "agent/record_answer_tool.py --questions.",
            )
        )
    for q in open_questions(config, data) if unanswered else []:
        findings.append(
            Finding(
                "QUESTION_UNANSWERED",
                shown,
                None,
                f"{q['id']} about {label(q['about'])} is not answered; the person answers it "
                "before checkpoint 2.",
            )
        )
    for q in data["questions"]:
        answer = q.get("answer")
        if answer and answer["choice"] == neither(q) and now.get(place(q["about"])) == q["asked"]:
            findings.append(
                Finding(
                    "QUESTION_UNANSWERED",
                    shown,
                    None,
                    f"{q['id']} was answered 'neither', but {label(q['about'])} is unchanged: "
                    "rewrite it, then check it again.",
                )
            )
    return findings


def _on_page(order: dict[str, int], key: tuple) -> tuple:
    """Where a question sits on the review page: its row, then its criterion."""
    row = key[1] if key[0] == "term" else key[0]
    return (order.get(row, len(order)), str(key[1]) if key[0] == "term" else key[1])


def checked(config: ProductConfig, data: dict) -> set[str]:
    """The criteria and terms checked: recorded by the check, unchanged since the
    latest approval of checkpoint 2, which the person read, or rewritten after
    their one recheck."""
    import tempfile

    from agent.render_review_tool import approved_config

    then, before = set(), set()
    with tempfile.TemporaryDirectory() as folder:
        approved = approved_config(config, Path(folder))
        if approved is not None:
            then = set(items(approved).values())
            with contextlib.suppress(ValueError):  # an unreadable file holds no earlier rounds
                before = {q["id"] for q in read_questions(approved)["questions"]}
    return set(data["checked"]) | then | _rechecked(config, data, before)


def _rechecked(config: ProductConfig, data: dict, before: set[str]) -> set[str]:
    """The criteria and terms settled at two texts since the latest approval — the
    check, then the recheck of its rewrite — and rewritten again: not checked a
    third time."""
    texts: dict[tuple, set[str]] = {}
    for q in data["questions"]:
        answer = q.get("answer")
        if q["id"] in before or not answer or answer["choice"] == neither(q):
            continue
        texts.setdefault(place(q["about"]), set()).add(q["asked"])
    now = items(config)
    return {now[k] for k, asked in texts.items() if len(asked) >= 2 and now.get(k) not in asked}


def unchecked(config: ProductConfig, data: dict | None = None) -> list[str]:
    """The criteria and terms to check, as lines; one rewritten to settle a question
    names it, so the check asks only about the wording the rewrite added."""
    data = read_questions(config) if data is None else data
    seen = checked(config, data)
    settled = {
        key: q
        for q in data["questions"]
        if q.get("answer") and q["answer"]["choice"] != neither(q)
        for key in places(q)
    }
    lines = []
    for key, sha in items(config).items():
        if sha in seen:
            continue
        line = label(_about(key))
        q = settled.get(key)
        if q is not None:
            reading = q["readings"][q["answer"]["choice"] - 1]["reading"]
            line += (
                f" — rewritten to settle {q['id']} ({reading}): ask only about wording the "
                "rewrite added"
            )
        lines.append(line)
    return lines


def _about(key: tuple) -> dict:
    return {"term": key[1]} if key[0] == "term" else {"requirement": key[0], "criterion": key[1]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--unchecked", action="store_true")
    mode.add_argument("--questions", type=Path)
    mode.add_argument("--question")
    mode.add_argument("--summary", action="store_true")
    mode.add_argument("--ask")
    parser.add_argument("--choice", type=int)
    parser.add_argument("--again", action="store_true")
    parser.add_argument("--approver")
    parser.add_argument("--role", choices=["architect", "reviewer", "customer"])
    args = parser.parse_args(argv)
    try:
        if args.unchecked:
            for line in unchecked(read_product_config(args.root)):
                print(line)
            return 0
        if args.questions:
            print(record_check(args.root, args.questions))
            return 0
        if args.ask:
            data = read_questions(read_product_config(args.root))
            found = next((q for q in data["questions"] if q["id"] == args.ask), None)
            if found is None:
                raise ValueError(f"no question {args.ask}")
            print(yaml.safe_dump(choice(found), sort_keys=False, allow_unicode=True), end="")
            return 0
        if args.summary:
            for line in summary(read_product_config(args.root)):
                print(line)
            return 0
        if args.choice is None or not args.approver or not args.role:
            parser.error("--question needs --choice, --approver and --role")
        print(
            record_answer(
                args.root, args.question, args.choice, args.approver, args.role, args.again
            )
        )
        return 0
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
