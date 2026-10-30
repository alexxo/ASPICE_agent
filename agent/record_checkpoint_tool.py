"""Merge a checkpoint's pull request once the architect approved it on the code host.

The person decides on the code host, never in the agent's session (v4.0.0): the
work of checkpoint <n> travels in a pull request from branch checkpoint/<n>, and
qf.yaml review.architect approves its head — at checkpoint 5 on behalf of the
customer, qf.yaml customer — or requests changes with the reason. This tool
waits for that decision and never takes it: it reads the architect's review of
the head and the crossing sign (qf/merge), and once the architect approved the
head and the sign says Ready to merge, it merges with a merge commit. That
merge commit is the record: the approval is read from git history
(read_approvals_tool), and verify_delivery_reviewed_gate checks every such merge
against the host (UNAPPROVED_MERGE). The watcher opens the pull request in the
browser while it waits for the person. A merge at checkpoint 2 is refused while
the review page is missing or differs from what the files render now, or while
a criterion is unchecked or a question unanswered; at checkpoint 1 while the
diagrams review page is not current. At checkpoint 5 the release workflow then
tags the merge and publishes the GitHub Release, and this tool opens it.

    python agent/record_checkpoint_tool.py --checkpoint N --pull-request N [--root PRODUCT]

It checks every 30 seconds until the architect decides: exit 0 merged, 4 changes
requested — the reason is printed, the findings for the next run.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.read_stages_tool import read_stages  # noqa: E402
from agent.record_answer_tool import question_findings  # noqa: E402
from agent.render_diagram_review_tool import diagram_review_page  # noqa: E402
from agent.render_diagram_review_tool import render as render_diagrams  # noqa: E402
from agent.render_review_tool import render, review_page  # noqa: E402
from tools.post_merge_status_tool import READY  # noqa: E402
from tools.read_approvals_tool import approval_state, checkpoint_of  # noqa: E402
from tools.read_host_tool import Host, HostError, read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig, read_product_config  # noqa: E402
from tools.render_page_tool import open_page  # noqa: E402
from tools.write_release_tool import pending  # noqa: E402

__all__ = ["ChangesRequested", "Checkpoint", "Waiting", "current_approval"]

POLL = 30  # seconds between two looks at the host
RELEASE_WAIT = 15 * 60  # seconds the release workflow may take to publish the release


class Waiting(Exception):
    """The architect has not approved the head yet, or the sign is not ready."""


class ChangesRequested(Exception):
    """The architect requested changes on the head: the reason is the finding."""


def _approves(checkpoint: int) -> str:
    for s in read_stages():
        if s.checkpoint == checkpoint and s.checkpoint_on_host:
            what = s.approves.replace("_", " ")
            raise ValueError(
                f"checkpoint {checkpoint} is a person's review of the {what} on the code host "
                "that CI asks for, not a checkpoint pull request"
            )
        if s.checkpoint == checkpoint:
            return s.approves
    raise ValueError(f"no stage closes with checkpoint {checkpoint}")


def _merge(repo: str, number: int, head: str) -> None:
    """Merge with a merge commit, only while the head is the approved one."""
    subprocess.run(
        ["gh", "pr", "merge", str(number), "--repo", repo, "--merge"]
        + ["--match-head-commit", head],
        check=True,
    )


@dataclass
class Checkpoint:
    """One checkpoint's pull request, from the architect's decision to the merge."""

    root: Path
    checkpoint: int
    number: int
    host: Host = field(default_factory=read_host)
    merge: Callable[[str, int, str], None] = _merge
    opener: Callable = open_page

    def decide(self) -> str:
        """Merge once the architect approved the head and the sign is ready; the
        merged head. Waiting while they have not; ChangesRequested with their reason."""
        config = read_product_config(self.root)
        approves = _approves(self.checkpoint)
        repo = repository(self.root)
        pull = self.host.pull_request(repo, self.number)
        if pull is None:
            raise ValueError(f"{repo} has no pull request #{self.number}")
        if checkpoint_of(pull.branch) != self.checkpoint:
            raise ValueError(
                f"#{self.number} comes from branch {pull.branch or 'unknown'}: the work of "
                f"checkpoint {self.checkpoint} travels from branch checkpoint/{self.checkpoint}"
            )
        if pull.merged:
            return pull.head
        architect = config.review_architect
        latest = [
            r
            for r in pull.reviews
            if r.author == architect and r.state in ("APPROVED", "CHANGES_REQUESTED")
        ]
        review = latest[-1] if latest and latest[-1].commit == pull.head else None
        if review is None:
            raise Waiting(
                f"checkpoint {self.checkpoint} waits for {architect}'s review of the head of "
                f"#{self.number}: Approve, or Request changes with the reason"
            )
        if review.state == "CHANGES_REQUESTED":
            raise ChangesRequested(review.body.strip() or "changes requested, no reason given")
        if _git(self.root, "rev-parse", "HEAD") != pull.head:
            raise ValueError(
                f"the product is not at the approved head {pull.head[:7]} of #{self.number}: "
                "check it out, so what is merged is what is checked"
            )
        if approves == "requirements":
            _reviewed(config)
        if approves == "diagrams":
            _current(
                config, diagram_review_page(config), render_diagrams, "render_diagram_review_tool"
            )
        sign = self.host.merge_sign(repo, pull.head)
        if sign != READY:
            raise Waiting(
                f"{architect} approved #{self.number}; it waits for the crossing sign "
                f"(qf/merge: {sign or 'none yet'})"
            )
        self.merge(repo, self.number, pull.head)
        return pull.head

    def release_page(self, version: str, deadline: float) -> str | None:
        """The GitHub Release the release workflow publishes, opened once it exists."""
        repo = repository(self.root)
        while True:
            page = self.host.release_page(repo, f"v{version}")
            if page is not None:
                return self.opener(page)
            if time.monotonic() >= deadline:
                return None
            time.sleep(POLL)


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
) -> tuple[object | None, str]:
    """The approval that counts and still matches the files, or None and why not."""
    state = approval_state(config, checkpoint, approves)
    return (state.merge if state.status == "approved" else None), state.reason


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--checkpoint", type=int, required=True)
    parser.add_argument("--pull-request", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        step = Checkpoint(args.root, args.checkpoint, args.pull_request)
        versions = pending(read_product_config(args.root))
        said = None
        while True:
            try:
                head = step.decide()
                break
            except Waiting as wait:
                if str(wait) != said:
                    print(str(wait), flush=True)
                    said = str(wait)
                time.sleep(POLL)
    except ChangesRequested as reason:
        print(f"Changes requested: {reason}")
        return 4
    except (ValueError, HostError, subprocess.CalledProcessError) as err:
        print(str(err), file=sys.stderr)
        return 1
    print(f"#{args.pull_request} merged at its approved head {head[:7]}.")
    if args.checkpoint == 5 and versions:
        page = step.release_page(versions[0], time.monotonic() + RELEASE_WAIT)
        print(f"Release {versions[0]}: {page or 'not published yet: see the release workflow'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
