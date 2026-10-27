"""Print a decision for a person, always in the same plain pattern (choice.v1).

Every decision the framework puts to a person — a question of a round, a
checkpoint, an escalation, a review item on the code host, a stopped review —
is one choice.v1: the question, the options explained in sentences, the
options to select by number, and a proposal when something decides one. This
tool checks it and prints it; the agent shows what it prints as it is, and
takes only a listed number, or Y where a proposal is offered.

    Question: What happens when the user enters a wrong password?
    Options: We could block the account immediately, or give the user two more chances.
    Select your option: 1. block immediately, 2. give two more chances
    Proposed: 2. give two more chances — the sign-in diagram shows three attempts.
    Your answer [Y / 1 / 2]:

    python agent/ask_person_tool.py --file CHOICE.yaml [--markdown]
        prints the choice; --markdown with a box per option, for the code host
    python agent/ask_person_tool.py --file CHOICE.yaml --answer TEXT
        prints the number the answer selects; exits 1 when it selects none:
        ask again
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from tools.validate_contract_tool import validate  # noqa: E402

__all__ = ["check", "read_choice", "render", "reply"]


def check(choice: object) -> dict:
    """The choice, when it is a valid choice.v1 whose proposal is one of its options;
    else ValueError naming the first problem."""
    violations = validate(choice, "choice")
    if violations:
        first = violations[0]
        where = first.path or "the choice"
        raise ValueError(f"not a valid choice.v1 at '{where}': {first.message}")
    proposal = choice.get("proposal")
    if proposal and proposal["choice"] > len(choice["select"]):
        raise ValueError("the proposal is not one of the options")
    return choice


def read_choice(path: Path) -> dict:
    """A choice.v1 from a YAML file, or '-' for standard input."""
    text = sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    try:
        return check(yaml.safe_load(text))
    except yaml.YAMLError as err:
        raise ValueError(f"{path} does not read: {err}") from err


def render(choice: dict, markdown: bool = False) -> str:
    """The choice in its pattern: in the terminal, or in Markdown with a box per
    option, which the person ticks on the code host."""
    select = choice["select"]
    proposal = choice.get("proposal")
    proposed = (
        f"{proposal['choice']}. {select[proposal['choice'] - 1]} — {proposal['why'].rstrip('.')}."
        if proposal
        else ""
    )
    if markdown:
        boxes = "\n".join(f"- [ ] {i}. {label}" for i, label in enumerate(select, 1))
        parts = [
            f"**Question:** {choice['question']}",
            f"**Options:** {choice['options']}",
            f"**Select your option:**\n{boxes}",
        ]
        if proposal:
            parts.append(f"**Proposed:** {proposed}")
        return "\n\n".join(parts)
    numbers = " / ".join(str(i) for i in range(1, len(select) + 1))
    lines = [
        f"Question: {choice['question']}",
        f"Options: {choice['options']}",
        "Select your option: " + ", ".join(f"{i}. {label}" for i, label in enumerate(select, 1)),
    ]
    if proposal:
        lines.append(f"Proposed: {proposed}")
    lines.append(f"Your answer [{'Y / ' if proposal else ''}{numbers}]:")
    return "\n".join(lines)


def reply(choice: dict, text: str) -> int | None:
    """The option an answer selects: a listed number, or Y for the proposal; None
    for anything else."""
    answer = text.strip()
    if answer.lower() == "y":
        proposal = choice.get("proposal")
        return proposal["choice"] if proposal else None
    if answer.isdigit() and 1 <= int(answer) <= len(choice["select"]):
        return int(answer)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--answer")
    args = parser.parse_args(argv)
    try:
        choice = read_choice(args.file)
    except (ValueError, OSError) as err:
        print(str(err), file=sys.stderr)
        return 2
    if args.answer is None:
        print(render(choice, args.markdown))
        return 0
    selected = reply(choice, args.answer)
    if selected is None:
        allowed = ("Y or " if choice.get("proposal") else "") + f"1 to {len(choice['select'])}"
        print(f"'{args.answer}' selects no option: answer {allowed}.", file=sys.stderr)
        return 1
    print(selected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
