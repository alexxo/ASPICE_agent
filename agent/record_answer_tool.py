"""Record the check for unclear criteria, and the person's answer to each question.

Before checkpoint 2 a session that sees only the requirements, the glossary and
the approved diagrams (agent/clarify_criteria_prompt.md) flags each acceptance
criterion, or glossary term, whose readings would need different tests. Its
questions and the person's answers live in <requirements_dir>/questions.yaml
(question.v1), with the SHA-256 of every criterion and term the check has seen:
one left unchanged is never asked about again.

    python agent/record_answer_tool.py --unchecked [--root PRODUCT]
        prints the criteria and terms the check has not seen yet
    python agent/record_answer_tool.py --questions FILE [--root PRODUCT]
        records the session's questions (a YAML list, without id and asked)
        and every criterion and term as checked
    python agent/record_answer_tool.py --question Q1 --choice N --approver NAME \\
        --role ROLE [--root PRODUCT]
        records the person's answer: a reading's number, or the one after the
        last for 'neither: the requirement goes back to be rewritten'

An unanswered question whose criterion or term changed since it was asked no
longer counts: the changed text is unchecked, and is checked again (§ 5 stages 1
and 2, rule 27).
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
    "items",
    "label",
    "neither",
    "open_questions",
    "place",
    "question_findings",
    "questions_file",
    "read_questions",
    "record_answer",
    "record_check",
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
        try:
            sha = now[place(entry["about"])]
        except KeyError:
            raise ValueError(
                f"{label(entry['about'])}: no such criterion or glossary term"
            ) from None
        number += 1
        data["questions"].append({"id": f"Q{number}", **entry, "asked": sha})
        proposal = entry.get("proposal")
        if isinstance(proposal, dict) and not 1 <= proposal.get("choice", 0) <= len(
            entry.get("readings") or []
        ):
            raise ValueError(f"Q{number}: the proposal is not one of its readings")
    data["checked"] = sorted(set(data["checked"]) | set(now.values()))
    return _write(config, data)


def record_answer(root: Path, question: str, choice: int, approver: str, role: str) -> Path:
    """Record the person's answer to one open question."""
    config = read_product_config(root)
    data = read_questions(config)
    found = next((q for q in data["questions"] if q["id"] == question), None)
    if found is None:
        raise ValueError(f"no question {question}")
    if found not in open_questions(config, data):
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
    unchecked = [k for k, sha in now.items() if sha not in set(data["checked"])]
    if unchecked:
        names = ", ".join(label(_about(k)) for k in unchecked[:8])
        more = f" and {len(unchecked) - 8} more" if len(unchecked) > 8 else ""
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


def _about(key: tuple) -> dict:
    return {"term": key[1]} if key[0] == "term" else {"requirement": key[0], "criterion": key[1]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--unchecked", action="store_true")
    mode.add_argument("--questions", type=Path)
    mode.add_argument("--question")
    parser.add_argument("--choice", type=int)
    parser.add_argument("--approver")
    parser.add_argument("--role", choices=["architect", "reviewer", "customer"])
    args = parser.parse_args(argv)
    try:
        if args.unchecked:
            config = read_product_config(args.root)
            checked = set(read_questions(config)["checked"])
            for key, sha in items(config).items():
                if sha not in checked:
                    print(label(_about(key)))
            return 0
        if args.questions:
            print(record_check(args.root, args.questions))
            return 0
        if args.choice is None or not args.approver or not args.role:
            parser.error("--question needs --choice, --approver and --role")
        print(record_answer(args.root, args.question, args.choice, args.approver, args.role))
        return 0
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
