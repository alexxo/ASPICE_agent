"""Post the reviewer agent's review of a pull request, with the checklist in its fixed form.

The reviewer agent posts from its own account — its token in QF_HOST_TOKEN for
its session — never the author's: GitHub forbids approving one's own pull
request, and verify_delivery_reviewed_gate counts only approvals from the accounts in
qf.yaml review.agents. The review is given on the pull request's current head.
An approval needs every checklist item checked; a request for changes names the
items that fail (--failing) and the findings (--findings, a text file).

    python tools/post_review_tool.py --pull-request N --decision approve
    python tools/post_review_tool.py --pull-request N --decision request_changes \\
        --failing correctness --findings findings.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.read_host_tool import API, HOST_TOKEN, GitHubHost, HostError, repository  # noqa: E402

__all__ = ["CHECKLIST", "MARK", "checklist", "render"]

CHECKLIST = ("correctness", "style", "traceability", "logging")
MARK = "<!-- qf-review-checklist -->"
_ITEM = re.compile(r"^\s*- \[([ xX])\] (\w+)\s*$")


def render(failing: set[str], findings: str = "") -> str:
    """The review body: the checklist, then the findings."""
    lines = [MARK] + [f"- [{' ' if item in failing else 'x'}] {item}" for item in CHECKLIST]
    text = "\n".join(lines)
    return f"{text}\n\n{findings.strip()}\n" if findings.strip() else f"{text}\n"


def checklist(body: str) -> dict[str, bool] | None:
    """Each item of the review's checklist and whether it is checked; None
    without the checklist."""
    if MARK not in body:
        return None
    items: dict[str, bool] = {}
    for line in body.split(MARK, 1)[1].splitlines():
        found = _ITEM.match(line)
        if found:
            items[found.group(2)] = found.group(1) != " "
        elif items and line.strip():
            break
    return items


def _post(token: str, repo: str, number: int, head: str, event: str, body: str) -> None:
    request = urllib.request.Request(
        f"{os.environ.get('GITHUB_API_URL', API).rstrip('/')}/repos/{repo}/pulls/{number}/reviews",
        data=json.dumps({"commit_id": head, "event": event, "body": body}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30):
            pass
    except urllib.error.HTTPError as err:
        raise HostError(f"GitHub refused the review: HTTP {err.code}") from err


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--pull-request", type=int, required=True)
    parser.add_argument("--decision", choices=["approve", "request_changes"], required=True)
    parser.add_argument("--failing", nargs="*", default=[], choices=CHECKLIST)
    parser.add_argument("--findings", type=Path, help="text file with the findings")
    args = parser.parse_args(argv)
    findings = args.findings.read_text() if args.findings else ""
    if args.decision == "approve" and args.failing:
        parser.error("an approval needs every checklist item checked")
    if args.decision == "request_changes" and not (args.failing and findings.strip()):
        parser.error("a request for changes names the failing items and the findings")
    token = os.environ.get(HOST_TOKEN)
    if not token:
        print(f"No {HOST_TOKEN}: set it to the reviewer agent's own token.", file=sys.stderr)
        return 2
    try:
        repo = repository(args.root)
        host = GitHubHost(token, os.environ.get("GITHUB_API_URL", API))
        pull = host.pull_request(repo, args.pull_request)
        if pull is None:
            print(f"No pull request {args.pull_request} in {repo}.", file=sys.stderr)
            return 2
        event = "APPROVE" if args.decision == "approve" else "REQUEST_CHANGES"
        _post(token, repo, pull.number, pull.head, event, render(set(args.failing), findings))
    except HostError as err:
        print(err, file=sys.stderr)
        return 2
    print(f"{args.decision} posted on {repo}#{pull.number} at {pull.head[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
