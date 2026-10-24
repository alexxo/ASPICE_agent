"""Post the reviewer agent's review of a pull request, with the checklist in its fixed form.

The reviewer agent posts from its own account — its token in QF_HOST_TOKEN for
its session — never the author's: GitHub forbids approving one's own pull
request, and verify_delivery_reviewed_gate counts only approvals from the accounts in
qf.yaml review.agents. The review is given on the pull request's current head.
An approval needs every checklist item the pull request asks for checked
(required_items: logging only when it changes code) and the review record
(--record, a review.v1 YAML file): whether the reviewer asks for a person, what
became of every finding, and the tests described for the person's review; it
goes into the body as a ```yaml review block. A request for changes names the
items that fail (--failing) and the findings (--findings, a text file).

    python tools/post_review_tool.py --pull-request N --decision approve --record review.yaml
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
from tools.read_product_config_tool import (  # noqa: E402
    ConfigError,
    ProductConfig,
    read_product_config,
)

__all__ = ["CHECKLIST", "MARK", "checklist", "render", "required_items"]

CHECKLIST = ("correctness", "style", "traceability", "logging")
MARK = "<!-- qf-review-checklist -->"
_ITEM = re.compile(r"^\s*- \[([ xX])\] (\w+)\s*$")


def required_items(config: ProductConfig, files) -> tuple[str, ...]:
    """The checklist items a pull request's review answers: every one, but logging
    only when the pull request changes a file under paths.code_dir."""
    code = config.relative(config.code_dir).rstrip("/") + "/"
    if any(f.startswith(code) for f in files):
        return CHECKLIST
    return tuple(item for item in CHECKLIST if item != "logging")


def render(
    failing: set[str],
    findings: str = "",
    items: tuple[str, ...] = CHECKLIST,
    record: dict | None = None,
) -> str:
    """The review body: the checklist, the findings, then the review record."""
    lines = [MARK] + [f"- [{' ' if item in failing else 'x'}] {item}" for item in items]
    text = "\n".join(lines) + "\n"
    if findings.strip():
        text += f"\n{findings.strip()}\n"
    if record is not None:
        import yaml

        dumped = yaml.safe_dump(record, sort_keys=False, allow_unicode=True)
        text += f"\n```yaml review\n{dumped}```\n"
    return text


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
    parser.add_argument("--record", type=Path, help="the review record, a review.v1 YAML file")
    args = parser.parse_args(argv)
    findings = args.findings.read_text() if args.findings else ""
    if args.decision == "approve" and args.failing:
        parser.error("an approval needs every checklist item checked")
    if args.decision == "approve" and not args.record:
        parser.error("an approval carries the review record (--record)")
    record = None
    if args.record:
        import yaml

        from tools.validate_contract_tool import validate

        record = yaml.safe_load(args.record.read_text())
        problems = validate(record, "review")
        if problems:
            where = problems[0].path or "the record"
            parser.error(f"{args.record} breaks review.v1 at '{where}': {problems[0].message}")
    if args.decision == "request_changes" and not (args.failing and findings.strip()):
        parser.error("a request for changes names the failing items and the findings")
    token = os.environ.get(HOST_TOKEN)
    if not token:
        print(f"No {HOST_TOKEN}: set it to the reviewer agent's own token.", file=sys.stderr)
        return 2
    try:
        config = read_product_config(args.root)
    except ConfigError as err:
        print(err, file=sys.stderr)
        return 2
    try:
        repo = repository(args.root)
        host = GitHubHost(token, os.environ.get("GITHUB_API_URL", API))
        pull = host.pull_request(repo, args.pull_request)
        if pull is None:
            print(f"No pull request {args.pull_request} in {repo}.", file=sys.stderr)
            return 2
        items = required_items(config, pull.files)
        extra = sorted(set(args.failing) - set(items))
        if extra:
            print(
                f"{', '.join(extra)}: not asked of {repo}#{pull.number}, which changes no code.",
                file=sys.stderr,
            )
            return 2
        event = "APPROVE" if args.decision == "approve" else "REQUEST_CHANGES"
        body = render(set(args.failing), findings, items, record)
        _post(token, repo, pull.number, pull.head, event, body)
    except HostError as err:
        print(err, file=sys.stderr)
        return 2
    print(f"{args.decision} posted on {repo}#{pull.number} at {pull.head[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
