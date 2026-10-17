"""Count a stage's attempts: the first run plus 3 retries in a row, then the architect.

Every attempt's gate results are logged to .qf/attempts/<stage>/attempt-<n>.json
in the product (ignored by git), so the agent can resume and the escalation
carries the findings of every attempt of the round. Only consecutive failing
attempts count: an attempt whose gates pass ends the round, so the next failure
starts a new one with the full budget. After the fourth failing attempt in a row
the decision is escalate, and an escalation report for the architect is written
next to the log.

    python agent/count_retries_tool.py record --stage ID [--root PRODUCT] < results.json
    python agent/count_retries_tool.py decide --stage ID [--root PRODUCT]
    python agent/count_retries_tool.py reset  --stage ID [--root PRODUCT]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.read_stages_tool import UnknownStage, stage  # noqa: E402

__all__ = ["ATTEMPTS_DIR", "MAX_RETRIES", "decide", "record_attempt", "reset"]

MAX_RETRIES = 3
ATTEMPTS_DIR = Path(".qf") / "attempts"


def _dir(root: Path, stage_id: str) -> Path:
    return Path(root) / ATTEMPTS_DIR / stage_id


def _attempts(root: Path, stage_id: str) -> list[list[dict]]:
    directory = _dir(root, stage_id)
    files = sorted(directory.glob("attempt-*.json"), key=lambda p: int(p.stem.split("-")[1]))
    return [json.loads(p.read_text(encoding="utf-8")) for p in files]


def record_attempt(root: Path, stage_id: str, gate_results: list[dict]) -> int:
    """Log one attempt's gate results; return its number (1 = the first run)."""
    directory = _dir(root, stage_id)
    directory.mkdir(parents=True, exist_ok=True)
    number = len(_attempts(root, stage_id)) + 1
    (directory / f"attempt-{number}.json").write_text(json.dumps(gate_results, indent=2))
    return number


def decide(root: Path, stage_id: str) -> dict:
    attempts = _attempts(root, stage_id)
    state = {"stage": stage_id, "attempts": len(attempts), "escalation_report": None}
    if not attempts:
        return {**state, "decision": "run", "retries_left": MAX_RETRIES}
    if _passed(attempts[-1]):
        return {**state, "decision": "pass", "retries_left": MAX_RETRIES}
    round_ = _round(attempts)
    retries_used = len(round_) - 1
    if retries_used < MAX_RETRIES:
        return {**state, "decision": "retry", "retries_left": MAX_RETRIES - retries_used}
    report = _dir(root, stage_id) / "escalation.md"
    report.write_text(_report(stage_id, round_), encoding="utf-8")
    return {
        **state,
        "decision": "escalate",
        "retries_left": 0,
        "escalation_report": report.relative_to(Path(root)).as_posix(),
    }


def _passed(results: list[dict]) -> bool:
    return all(r["result"] == "pass" for r in results)


def _round(attempts: list[list[dict]]) -> list[tuple[int, list[dict]]]:
    """The failing attempts since the last passing one, with their numbers."""
    numbered = list(enumerate(attempts, start=1))
    last_pass = max((n for n, results in numbered if _passed(results)), default=0)
    return numbered[last_pass:]


def reset(root: Path, stage_id: str) -> None:
    """Start a new round, after the architect has fixed the work or given guidance."""
    shutil.rmtree(_dir(root, stage_id), ignore_errors=True)


def _report(stage_id: str, round_: list[tuple[int, list[dict]]]) -> str:
    lines = [
        f"# Escalation — stage {stage_id}",
        "",
        f"The gates still fail after the first run and {MAX_RETRIES} retries in a row. Fix "
        "the work, give guidance for another round, or stop. Findings of every attempt of "
        "the round:",
    ]
    for number, results in round_:
        lines += ["", f"## Attempt {number}", ""]
        for gate in results:
            for f in gate["findings"]:
                where = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
                lines.append(f"- `{f['gate']}` {f['rule']} — {where} — {f['message']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["record", "decide", "reset"])
    parser.add_argument("--stage", required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        args.stage = stage(args.stage).id  # one counter per stage, named by id or number
    except UnknownStage as err:
        print(str(err), file=sys.stderr)
        return 2
    if args.action == "record":
        doc = json.load(sys.stdin)
        record_attempt(args.root, args.stage, doc.get("gates", doc))
    elif args.action == "reset":
        reset(args.root, args.stage)
    print(json.dumps(decide(args.root, args.stage), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
