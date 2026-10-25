"""Post the checkpoint-4 review on a pull request a person must review, in plain words.

CI posts it as a comment on the pull request once the reviewer agent has
approved the head with its review record (review.v1), when
classify_pull_request_tool finds the pull request important or risky (rule 14
of the quality assurance stage). Never written by the author, and readable
without code: it mentions qf.yaml review.people, so the host notifies them,
says what the pull request does (the record's summary), why they are asked in
one plain sentence, and how to answer, then lists the questions, each with a
pair of boxes, the first the answer yes; IDs, the head and the files are
folded under "Details for the record":

- each changed detailed design, as stories: one question per story that shows
  a requirement of criticality high or of kind security the design serves —
  the requirements' text next to the story's steps, told from the design
  alone, a gap marked ⚠ — and one per such requirement no story shows;
- each test the person reviews: the approved criteria next to the test told
  as given, when, then, from the test alone;
- each weakened test: before and now;
- each finding closed without a change: the finding, the author's answer and
  the reviewer's final position;
- the reviewer agent's own request, if any.

With nothing to tick, the comment still says who is asked and why, and that
the approval alone is the review. The person ticks one box per question — the
host saves each tick at once — then approves, or requests changes with the
reason. The comment names the head and a
digest of its items: one comment per pull request, rewritten when the head or
the items change, never otherwise, so an approval stays valid while nothing it
covered changed. verify_delivery_reviewed_gate reads the answers.

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

__all__ = ["MARK", "answers", "find_note", "render"]

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
    items = _items(config, repo, pull, review, record)
    body = "\n\n".join(
        f"### {i}. {title}\n\n{text}\n\n- [ ] {yes}\n- [ ] {no}"
        for i, (title, text, yes, no) in enumerate(items, 1)
    )
    people = " ".join(f"@{p}" for p in config.review_people)
    minutes = max(1, sum(2 if text.startswith(_STORY) else 1 for _, text, _, _ in items))
    why = "; ".join(review.brief or review.reasons)
    lines = [f"{people} — **your review is needed** (about {minutes} min)."]
    if record.get("summary"):
        lines.append(f"**What this pull request does:** {record['summary']}")
    lines.append(f"**Why you are asked:** {why[:1].upper()}{why[1:]}.")
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


_STORY = "**What must happen**"


def _items(
    config: ProductConfig, repo: str, pull: PullRequest, review, record: dict
) -> list[tuple]:
    from tools.read_requirements_tool import read_requirements

    ratings = {
        r.data["uid"]: r.data
        for r in read_requirements(config)
        if isinstance(r.data.get("uid"), str)
    }
    items = []
    for component in review.designs:
        items += _design_items(component, review.asked.get(component, []), record, ratings)
    for test in record.get("tests", []):
        if test["file"] not in review.tests:
            continue
        uids = review.requirements.get(test["file"], [])
        rated = [
            u
            for u in uids
            if ratings.get(u, {}).get("criticality") == "high"
            or ratings.get(u, {}).get("kind") == "security"
        ] or uids
        criteria = "\n".join(_criteria(u, ratings.get(u, {})) for u in rated) or (
            "- no requirement named"
        )
        items.append(
            (
                f"Test: {test['test']}",
                f"{_STORY}\n{criteria}\n\n**What the test does**, told from the test alone:\n"
                f"- *Given* {test['prepares']}\n- *When* {test['does']}\n"
                f"- *Then it checks* {test['checks']}\n- *It does not check:* {test['not']}",
                "the test checks what must happen",
                "it does not",
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


def _design_items(component: str, asked: list[str], record: dict, ratings: dict) -> list[tuple]:
    """One question per story that shows a requirement the person is asked about,
    with those requirements; one per asked requirement no story shows. Without
    such requirements, one question with all the design's stories."""
    stories = [s for s in record.get("stories", []) if s["design"] == component]
    covers = record.get("covers", {})
    told = "**What the design makes happen**, told from the design alone:\n"
    if not asked:
        text = "\n\n".join(f"*{s['story']}*\n{_steps(s)}" for s in stories) or (
            "The reviewer agent's record tells no story of this design."
        )
        return [
            (
                f"The design of {component}",
                f"{told}\n{text}",
                "this is what must happen",
                "it is not",
            )
        ]
    items = []
    for story in stories:
        uids = [u for u in asked if covers.get(u) == story["story"]]
        if uids:
            criteria = "\n".join(_criteria(u, ratings.get(u, {})) for u in uids)
            items.append(
                (
                    story["story"],
                    f"{_STORY}\n{criteria}\n\n{told}{_steps(story)}",
                    "this is what must happen",
                    "it is not",
                )
            )
    titles = {s["story"] for s in stories}
    for uid in asked:
        if covers.get(uid) not in titles:
            items.append(
                (
                    f"No story of {component} shows this requirement",
                    f"{_STORY}\n{_criteria(uid, ratings.get(uid, {}))}\n\nThe reviewer agent "
                    "found no situation of the design that shows it.",
                    "acceptable: not this design's work",
                    "the design must show it",
                )
            )
    return items


def _steps(story: dict) -> str:
    return "\n".join(
        f"{i}. {'⚠ ' if step.get('gap') else ''}{step['text']}"
        for i, step in enumerate(story["steps"], 1)
    )


def _criteria(uid: str, data: dict) -> str:
    rating = ", ".join(x for x in (data.get("criticality"), data.get("kind")) if x)
    statement = data.get("statement", "")
    lines = [f"- “{statement}” ({rating}, {uid})" if statement else f"- {uid} ({rating})"]
    for c in data.get("acceptance_criteria", []):
        if isinstance(c, dict):
            lines.append(
                f"  - *Given* {c.get('given')} · *When* {c.get('when')} · *Then* {c.get('then')}"
            )
    return "\n".join(lines)


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
    expected = render(config, repo, pull, person_review(config, pull, record), record)
    if expected is None:
        print("No person's review is needed: nothing to post.")
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
