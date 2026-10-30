"""Copy a person's decision at a checkpoint from the code host, and find the decision that counts.

The person decides on the code host: Approve, or Request changes with the
reason, on the pull request that brings the work (checkpoints 1, 2, 3 and 5;
FB-69). This tool reads that review and copies it — who, which review, on
which commit — so the agent never decides in the person's name and the person
never pastes a command; with no review yet, it opens the pull request's
changes in the browser and says it waits. The copy is written as approval.v1 to
<approvals_dir>/<date>-checkpoint-<n>-<subject>.yaml, with the SHA-256 of every
file it covers, so it is bound to the exact content reviewed. The latest file
for a checkpoint and subject counts; it is current only while every covered file
is unchanged and no file was added or removed. An approval at checkpoint 2 is
refused while the review page is missing or differs from what the files render
now, or while a criterion is unchecked or a question unanswered: the person
approves the requirements they saw, with every question settled.

A copy is written only while the files it covers are what the reviewed commit
holds; CI checks the review it names on the host (verify_delivery_reviewed_gate,
UNPROVEN_CHECKPOINT_DECISION).

    python agent/record_checkpoint_tool.py --checkpoint N --pull-request N [--root PRODUCT]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from agent.read_stages_tool import read_stages  # noqa: E402
from agent.record_answer_tool import question_findings  # noqa: E402
from agent.render_diagram_review_tool import diagram_review_page  # noqa: E402
from agent.render_diagram_review_tool import render as render_diagrams  # noqa: E402
from agent.render_review_tool import render, review_page  # noqa: E402
from tools.read_approvals_tool import approval_state, sha256, subject_files  # noqa: E402
from tools.read_host_tool import Host, HostError, Review, read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig, read_product_config  # noqa: E402
from tools.render_page_tool import open_page  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

__all__ = ["Waiting", "current_approval", "record_checkpoint", "record_from_host", "subject_files"]

DECISIONS = {"APPROVED": "approved", "CHANGES_REQUESTED": "changes-requested"}


class Waiting(Exception):
    """No person's review counts yet: the person decides on the code host."""


def _approves(checkpoint: int) -> str:
    for s in read_stages():
        if s.checkpoint == checkpoint and s.checkpoint_on_host:
            what = s.approves.replace("_", " ")
            raise ValueError(
                f"checkpoint {checkpoint} is a person's review of the {what} on the code host, "
                "not a recorded file: approve it there"
            )
        if s.checkpoint == checkpoint:
            return s.approves
    raise ValueError(f"no stage closes with checkpoint {checkpoint}")


def record_checkpoint(
    root: Path,
    checkpoint: int,
    decision: str,
    approver: str,
    role: str,
    comment: str | None = None,
    now: datetime | None = None,
    review: dict | None = None,
) -> Path:
    """Write the record of a decision; record_from_host gives its facts from the host."""
    config = read_product_config(root)
    approves = _approves(checkpoint)
    if approves == "requirements" and decision == "approved":
        _reviewed(config)
    if approves == "diagrams" and decision == "approved":
        _current(config, diagram_review_page(config), render_diagrams, "render_diagram_review_tool")
    files = subject_files(config, approves)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    data = {
        "checkpoint": checkpoint,
        "decision": decision,
        "approver": {"name": approver, "role": role},
        "date": now.isoformat(timespec="seconds"),
        "subject": [{"path": config.relative(f), "sha256": sha256(f)} for f in files],
    }
    if comment:
        data["comment"] = comment
    if review:
        data["review"] = review
    violations = validate(data, "approval")
    if violations:
        first = violations[0]
        raise ValueError(f"not a valid approval at '{first.path or 'the record'}': {first.message}")
    config.approvals_dir.mkdir(parents=True, exist_ok=True)
    path = config.approvals_dir / f"{now:%Y-%m-%dT%H%M%SZ}-checkpoint-{checkpoint}-{approves}.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def record_from_host(
    root: Path,
    checkpoint: int,
    number: int,
    host: Host | None = None,
    now: datetime | None = None,
) -> Path:
    """Copy the person's latest decision on pull request number: an approval or a
    request for changes by a person — no review agent, no bot, not the author."""
    root = Path(root)
    config = read_product_config(root)
    approves = _approves(checkpoint)
    host = host or read_host()
    repo = repository(root)
    pull = host.pull_request(repo, number)
    if pull is None:
        raise ValueError(f"{repo} has no pull request #{number}")
    page = f"https://github.com/{repo}/pull/{number}/files"
    agents = set(config.review_agents)
    decided = [
        r
        for r in pull.reviews
        if r.state in DECISIONS and not r.bot and r.author not in agents | {pull.author}
    ]
    if not decided:
        raise Waiting(
            f"checkpoint {checkpoint} waits for a person's review of #{number}: Approve, or "
            f"Request changes with the reason, on {open_page(page)}"
        )
    review = decided[-1]
    for path in sorted(config.approvals_dir.glob(f"*-checkpoint-{checkpoint}-{approves}.yaml")):
        if (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("review", {}).get(
            "id"
        ) == review.id:
            return path  # copied already
    changed = _changed_since(config, approves, review)
    if changed:
        raise Waiting(
            f"{', '.join(changed)} changed since {review.author}'s review of "
            f"{review.commit[:7]}: checkpoint {checkpoint} waits for a review of the head on "
            f"{open_page(page)}"
        )
    return record_checkpoint(
        root,
        checkpoint,
        DECISIONS[review.state],
        review.author,
        "customer" if approves == "release" else "architect",
        review.body.strip() or None,
        now,
        {"pull_request": number, "id": review.id, "commit": review.commit},
    )


def _changed_since(config: ProductConfig, approves: str, review: Review) -> list[str]:
    """The files the decision covers that differ from the reviewed commit."""
    changed = []
    for f in subject_files(config, approves):
        path = config.relative(f)
        at = _git(config.root, "rev-parse", f"{review.commit}:{path}")
        now = _git(config.root, "hash-object", path)
        if at is None or at != now:
            changed.append(path)
    return changed


def _git(root: Path, *args: str) -> str | None:
    run = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else None


def _reviewed(config: ProductConfig) -> None:
    unsettled = question_findings(config)
    if unsettled:
        raise ValueError(
            f"{unsettled[0].message} An approval at checkpoint 2 waits until every criterion "
            "is checked and every question answered."
        )
    _current(config, review_page(config), render, "render_review_tool")


def _current(config: ProductConfig, page: Path, render_page, tool: str) -> None:
    """Refuse an approval on a page missing or not what the files render now."""
    if not page.is_file() or page.read_text(encoding="utf-8") != render_page(config):
        raise ValueError(
            f"{config.relative(page)} is missing or not what the files render now: render it "
            f"with agent/{tool}.py, commit it and have the person review it again"
        )


def current_approval(
    config: ProductConfig, checkpoint: int, approves: str
) -> tuple[Path | None, str]:
    """The approval that counts and still matches the files, or None and why not."""
    state = approval_state(config, checkpoint, approves)
    return (state.path if state.status == "approved" else None), state.reason


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--checkpoint", type=int, required=True)
    parser.add_argument("--pull-request", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        path = record_from_host(args.root, args.checkpoint, args.pull_request)
    except Waiting as wait:
        print(str(wait))
        return 3
    except (ValueError, HostError) as err:
        print(str(err), file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
