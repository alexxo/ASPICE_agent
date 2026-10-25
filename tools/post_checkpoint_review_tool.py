"""Post the checkpoint-4 review on a pull request a person must review, in plain words.

CI posts it as a comment on the pull request once the reviewer agent has
approved the head with its review record (review.v1), when
classify_pull_request_tool calls a person (rule 14 of the quality assurance
stage), after the verification report of the tree is written. Never written by
the author, and readable without code: it mentions qf.yaml review.people, so
the host notifies them, says what the pull request does (the record's
summary), why they are asked in one plain sentence, and how to answer, then
lists the questions, each with a pair of boxes, the first the answer yes; the
head and the files are folded under "Details for the record":

- checkpoint 4, the results, on the pull request that brings them (stage 8):
  one line per requirement it proves that is of criticality high or of kind
  security, and per requirement anywhere that did not pass — its text, its
  software-level tests told as given, when, then from the test alone, the
  measured values next to the threshold, and the result — answered achieved
  or not achieved; the other requirements only counted;
- the questions of what is wanted, on any pull request: each gap (⚠) a story
  of a changed design marks and the reviewer agent approved, so no
  requirement answers it — keep the requirements, or change them; each
  weakened test, before and now; each finding closed without a change, the
  finding, the author's answer and the reviewer's final position; the
  reviewer agent's own request.

With nothing to tick, the comment still says who is asked and why, and that
the approval alone is the review. The person ticks one box per question — the
host saves each tick at once — then approves, or requests changes with the
reason. The comment names the head and a digest of its items: one comment per
pull request, rewritten when the head or the items change, never otherwise,
so an approval stays valid while nothing it covered changed.
verify_delivery_reviewed_gate reads the answers.

    python tools/post_checkpoint_review_tool.py --root PRODUCT --pull-request N
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.read_host_tool import API, HOST_TOKEN, Note, PullRequest  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402

__all__ = ["MARK", "answers", "find_note", "render", "results_page"]

MARK = "<!-- qf-checkpoint-4-review -->"
_STAMP = re.compile(r"<!-- head: ([0-9a-f]+) items: ([0-9a-f]+) -->")
LONGEST = 65_000  # characters, under the host's longest comment (65,536)
_BOX = re.compile(r"^\s*- \[([ xX])\] (.+?)\s*$")
CONDITIONS = {
    1: "the rating looks too low",
    2: "the meaning is unclear",
    3: "beyond what was approved",
    4: "cannot be undone",
    5: "cannot be verified",
}


def render(config: ProductConfig, repo: str, pull: PullRequest, review, record: dict) -> str | None:
    """The comment for the pull request's head, or None when no person reviews it.
    With nothing to tick, it still says who is asked, why, and that the approval
    alone is the review."""
    if not review.needed:
        return None
    results = results_page(config, review, record) if review.proves else ([], "")
    if results is None:
        return None  # no verification report of this tree yet: nothing to approve
    items, counted = results
    items = items + _items(review)
    body = "\n\n".join(
        f"### {i}. {title}\n\n{text}\n\n- [ ] {yes}\n- [ ] {no}"
        for i, (title, text, yes, no) in enumerate(items, 1)
    )
    people = " ".join(f"@{p}" for p in config.review_people)
    minutes = max(1, len(items))
    why = "; ".join(review.brief or review.reasons)
    lines = [f"{people} — **your review is needed** (about {minutes} min)."]
    if record.get("summary"):
        lines.append(f"**What this pull request does:** {record['summary']}")
    lines.append(f"**Why you are asked:** {why[:1].upper()}{why[1:]}.")
    if counted:
        lines.append(f"**The results:** {counted}")
    if items:
        lines.append(
            "**How to answer:** tick one box per question — GitHub saves each tick at once — "
            "then **Review changes → Approve**, or **Request changes** and write why, for any "
            "*no*."
        )
    else:
        lines.append(
            "**How to answer:** nothing to tick. Look at the changes, then **Review changes → "
            "Approve**, or **Request changes** and write why."
        )
    shown = lines + ([body] if body else [])
    content = "\n\n".join(shown + [_details(pull, review, record)]) + "\n"
    if len(content) > LONGEST:
        details = (
            f"*Details for the record left out: the comment would exceed {LONGEST} characters.*"
        )
        content = "\n\n".join(shown + [details]) + "\n"
    digest = hashlib.sha256(content.encode()).hexdigest()[:16]
    return f"{MARK}\n<!-- head: {pull.head} items: {digest} -->\n{content}"


def _details(pull: PullRequest, review, record: dict) -> str:
    """What a machine reads and a person rarely needs, folded."""
    lines = [f"- Head: `{pull.head}`", f"- Why, in full: {'; '.join(review.reasons)}"]
    for story in record.get("stories", []):
        sources = "; ".join(
            f"step {i}: {', '.join(step['source'])}" for i, step in enumerate(story["steps"], 1)
        )
        lines.append(f"- Story *{story['story']}* ({story['design']}): {sources}")
    lines.append(f"- Files: {', '.join(pull.files)}")
    return (
        "<details><summary>Details for the record</summary>\n\n"
        + "\n".join(lines)
        + ("\n\n</details>")
    )


def _stamp(body: str) -> tuple[str, str] | None:
    found = _STAMP.search(body)
    return (found.group(1), found.group(2)) if found else None


def find_note(pull: PullRequest, expected: str) -> Note | None:
    """CI's comment for exactly this head and these items."""
    want = _stamp(expected)
    for note in pull.notes:
        if note.bot and MARK in note.body and _stamp(note.body) == want:
            return note
    return None


def answers(body: str) -> list[tuple[str, str | None]]:
    """Each item's title and its answer: yes, no, or None when unanswered (no box,
    or both ticked)."""
    found = []
    for section in re.split(r"^### ", body, flags=re.M)[1:]:
        title = section.splitlines()[0].strip()
        boxes = [m.group(1) != " " for m in map(_BOX.match, section.splitlines()) if m]
        if len(boxes) < 2 or boxes[0] == boxes[1]:
            found.append((title, None))
        else:
            found.append((title, "yes" if boxes[0] else "no"))
    return found


def results_page(config: ProductConfig, review, record: dict) -> tuple[list, str] | None:
    """The results of software verification, from the tree's verification report:
    one question per requirement this pull request proves that is of
    criticality high or of kind security, and per requirement anywhere that did
    not pass; the rest only counted. None without a report of this tree."""
    from tools.classify_pull_request_tool import important
    from tools.read_requirements_tool import read_requirements
    from tools.write_verification_report_tool import REPORT, report_dir

    folder = report_dir(config)
    report = folder / REPORT if folder else None
    if report is None or not report.is_file():
        return None
    rows = json.loads(report.read_text()).get("software", [])
    ratings = {
        r.data["uid"]: r.data
        for r in read_requirements(config)
        if isinstance(r.data.get("uid"), str)
    }
    proves = set(review.proves)
    asked = [
        r
        for r in rows
        if r["result"] not in ("passed", "sealed")
        or (r["requirement"] in proves and important(ratings.get(r["requirement"], {})))
    ]
    told = {}
    for test in record.get("tests", []):
        told.setdefault(test["file"], []).append(test)
    items = [_result(row, ratings.get(row["requirement"], {}), told) for row in asked]
    tally = {k: sum(1 for r in rows if r["result"] in v) for k, v in _TALLY.items()}
    counted = (
        f"{len(rows)} requirements · {tally['passed']} passed · {tally['failed']} failed · "
        f"{tally['not run']} not run. You tick {len(asked)}: the high-criticality and security "
        "ones this pull request proves, and every one that did not pass; the other "
        f"{len(rows) - len(asked)} are only counted."
    )
    return items, counted


_TALLY = {"passed": ("passed", "sealed"), "failed": ("failed",), "not run": ("missing",)}
_RESULT = {
    "passed": "passed",
    "sealed": "proved at checkpoint 3",
    "failed": "**failed**",
    "missing": "**not run**",
}


def _result(row: dict, data: dict, told: dict) -> tuple:
    uid = row["requirement"]
    rating = ", ".join(x for x in (data.get("criticality"), data.get("kind")) if x)
    lines = [f"({rating}, {uid})"]
    for file in row.get("tests", []):
        for test in told.get(file, []):
            lines.append(
                f"**The test, told from the test alone** ({test['test']}):\n"
                f"- *Given* {test['prepares']}\n- *When* {test['does']}\n"
                f"- *Then it checks* {test['checks']}\n- *It does not check:* {test['not']}"
            )
        if file not in told:
            lines.append(f"**The test:** {file}, not described")
    if row["proved_by"] == "measurement":
        values = ", ".join(f"{m['value']:g}" for m in row.get("measured", [])) or "none"
        lines.append(f"**Measured:** {values} (threshold {row['threshold']})")
    lines.append(f"**Result:** {_RESULT.get(row['result'], row['result'])}")
    statement = data.get("statement")
    return (
        f"“{statement}”" if statement else uid,
        "\n\n".join(lines),
        "achieved",
        "not achieved",
    )


def _items(review) -> list[tuple]:
    """The questions of what is wanted."""
    items = []
    for design, story, step in review.gaps:
        items.append(
            (
                f"An open question in the design of {design}",
                f"*{story}*\n⚠ {step}\n\nNo requirement asks for this, so the reviewer agent "
                "approved the design. Keep the requirements as they are — or change them: "
                "request changes and write what you want, and the agent proposes it as a change "
                "request.",
                "keep the requirements",
                "change them",
            )
        )
    for w in review.weakenings:
        items.append(
            (
                f"Weakened: {w.file}",
                f"*Before:* {w.before} · *Now:* {w.now}",
                "acceptable",
                "weakened, request changes",
            )
        )
    for d in review.disputes:
        items.append(
            (
                f"Disagreement ({d['outcome']})",
                f"*The reviewer found:* {d['finding']}\n"
                f"*The author answered:* {d.get('author_answer') or '—'}\n"
                f"*The reviewer's final position:* {d.get('reviewer_position') or 'withdrawn'}",
                "the author is right",
                "the reviewer is right",
            )
        )
    if review.request:
        condition = review.request["condition"]
        items.append(
            (
                "The reviewer agent asks for a person",
                f"*{condition} — {CONDITIONS[condition]}:* {review.request['reason']}",
                "acceptable",
                "needs changes",
            )
        )
    return items


def _send(token: str, url: str, method: str, body: str) -> None:
    request = urllib.request.Request(
        url,
        data=json.dumps({"body": body}).encode(),
        method=method,
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
    parser.add_argument("--pull-request", type=int, required=True)
    args = parser.parse_args(argv)
    from gates.sup.verify_delivery_reviewed_gate import person_review
    from tools.classify_pull_request_tool import review_record
    from tools.read_host_tool import HostError, read_host, repository
    from tools.read_product_config_tool import ConfigError, read_product_config

    token = os.environ.get(HOST_TOKEN)
    if not token:
        print(f"No {HOST_TOKEN}: CI sets it to the run's own token.", file=sys.stderr)
        return 2
    try:
        config = read_product_config(args.root)
        repo = os.environ.get("GITHUB_REPOSITORY") or repository(config.root)
        pull = read_host().pull_request(repo, args.pull_request)
    except (ConfigError, HostError) as err:
        print(err, file=sys.stderr)
        return 2
    if pull is None:
        print(f"No pull request {args.pull_request} in {repo}.", file=sys.stderr)
        return 2
    agents = set(config.review_agents)
    by_agent = [r for r in pull.approvals() if r.author in agents and r.author != pull.author]
    record = review_record(by_agent[-1].body)[0] if by_agent else None
    if record is None:
        print("No review record of the reviewer agent on this head yet: nothing to post.")
        return 0
    review = person_review(config, pull, record)
    expected = render(config, repo, pull, review, record)
    if expected is None:
        print(
            "No verification report of this tree yet: write it before posting the results."
            if review.needed
            else "No person's review is needed: nothing to post."
        )
        return 0
    if find_note(pull, expected) is not None:
        print("The checkpoint-4 review for this head is posted already.")
        return 0
    api = os.environ.get("GITHUB_API_URL", API).rstrip("/")
    mine = [n for n in pull.notes if n.bot and MARK in n.body]
    try:
        if mine:
            _send(token, f"{api}/repos/{repo}/issues/comments/{mine[-1].id}", "PATCH", expected)
        else:
            _send(token, f"{api}/repos/{repo}/issues/{pull.number}/comments", "POST", expected)
    except (urllib.error.URLError, OSError) as err:
        # Without the comment the gate waits (REVIEW_ITEMS_UNANSWERED): never a false pass.
        print(
            f"The checkpoint-4 review was not posted on {repo}#{pull.number}: {err}",
            file=sys.stderr,
        )
        return 0
    print(f"Checkpoint-4 review posted on {repo}#{pull.number} for {pull.head[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
