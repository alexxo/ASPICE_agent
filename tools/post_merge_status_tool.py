"""Post the crossing sign on a pull request's head: wait, or ready to merge.

The product's CI posts the commit status qf/merge (CONTEXT) on the pull
request's head, so the author agent, which merges, reads it in the pull
request's checks, as anyone can next to the merge button (rule 13 of the
quality assurance stage): pending
"Wait: gates running" when the gates start (--running), then, from the gates'
result (--stage-file, resolve_stage_tool's JSON), failure "Wait: <what is
missing>" or success "Ready to merge". A person's review names qf.yaml
review.people, why they are asked and what to do, e.g. "Wait: a review by
alexxo (it changes the quality gates' own files): approve on GitHub". A
status belongs to one commit, so a new push starts with no sign, and no sign
means wait. Merging on a sign other than "Ready to merge" is caught on the
main branch, as before (rule 12).

    python tools/post_merge_status_tool.py --sha HEAD_SHA --running
    python tools/post_merge_status_tool.py --sha HEAD_SHA --stage-file .qf/stage.json
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

from tools.read_host_tool import API, HOST_TOKEN, repository  # noqa: E402

__all__ = ["CONTEXT", "READY", "RUNNING", "sign"]

CONTEXT = "qf/merge"
RUNNING = "Wait: gates running"
READY = "Ready to merge"
LIMIT = 140  # GitHub's longest status description
# What a finding means the pull request still waits for, by rule; {review} is
# the person's review, named.
WAITS_FOR = {
    "MISSING_AGENT_REVIEW": "the reviewer agent's approval",
    "INCOMPLETE_CHECKLIST": "the reviewer agent's approval",
    "REVIEW_STORY_UNSOURCED": "the reviewer agent's approval",
    "MISSING_PERSON_APPROVAL": "{review}{why}: approve on GitHub",
    "REVIEW_ITEMS_UNANSWERED": "{review}: tick every item of its comment",
    "REVIEW_CHANGED_AFTER_APPROVAL": "{review}: approve again",
}
_WHY = re.compile(r"\(why: ([^)]*)\)")  # verify_delivery_reviewed_gate's short reason


def sign(state: dict | None, people=()) -> tuple[str, str]:
    """The commit status (state, description) for the gates' result; None when
    the gates did not finish. A person's review names the people."""
    review = f"a review by {' or '.join(people)}" if people else "a person's review"
    if state is None:
        return "failure", "Wait: gates red: the gates did not finish"
    findings = state.get("findings") or []
    if not findings:
        return "success", READY
    missing: list[str] = []
    red: list[str] = []
    order = list(WAITS_FOR)  # the person's review named once, by its first missing step
    for finding in sorted(
        findings, key=lambda f: order.index(f["rule"]) if f["rule"] in order else 0
    ):
        waits = WAITS_FOR.get(finding["rule"])
        if waits is not None:
            why = _WHY.search(finding.get("message", ""))
            waits = waits.format(review=review, why=f" ({why.group(1)})" if why else "")
            if waits.startswith(review) and any(m.startswith(review) for m in missing):
                continue
        if waits is None and finding["gate"] not in red:
            red.append(finding["gate"])
        elif waits is not None and waits not in missing:
            missing.append(waits)
    if red:
        missing.append(f"gates red: {', '.join(red)}")
    text = "Wait: " + "; ".join(missing)
    return "failure", text if len(text) <= LIMIT else text[: LIMIT - 1] + "…"


def _people(root: Path) -> tuple[str, ...]:
    """qf.yaml review.people; none when the configuration cannot be read."""
    from tools.read_product_config_tool import ConfigError, read_product_config

    try:
        return tuple(read_product_config(root).review_people)
    except ConfigError:
        return ()


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _post(token: str, repo: str, sha: str, state: str, description: str) -> None:
    body = {"state": state, "description": description, "context": CONTEXT}
    server, run = os.environ.get("GITHUB_SERVER_URL"), os.environ.get("GITHUB_RUN_ID")
    if server and run:
        body["target_url"] = f"{server}/{repo}/actions/runs/{run}"
    request = urllib.request.Request(
        f"{os.environ.get('GITHUB_API_URL', API).rstrip('/')}/repos/{repo}/statuses/{sha}",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--sha", required=True, help="the pull request's head commit")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--running", action="store_true", help="the gates are starting")
    which.add_argument("--stage-file", type=Path, help="resolve_stage_tool's JSON result")
    args = parser.parse_args(argv)
    token = os.environ.get(HOST_TOKEN)
    if not token:
        print(f"No {HOST_TOKEN}: CI sets it to the run's own token.", file=sys.stderr)
        return 2
    state, description = (
        ("pending", RUNNING) if args.running else sign(_read(args.stage_file), _people(args.root))
    )
    repo = os.environ.get("GITHUB_REPOSITORY") or repository(args.root)
    try:
        _post(token, repo, args.sha, state, description)
    except (urllib.error.URLError, OSError) as err:
        # No sign means wait: a run whose token cannot write statuses (a fork's)
        # leaves the pull request without one, never with a false "ready".
        print(f"The crossing sign was not posted on {repo}@{args.sha[:7]}: {err}", file=sys.stderr)
        return 0
    print(f"{CONTEXT}: {description}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
