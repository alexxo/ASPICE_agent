"""verify_delivery_reviewed_gate — SUP.1 BP1, SWE.1 BP6, SWE.2 BP5, SWE.3 BP5: deliveries reviewed.

The work travels in a pull request (NO_PULL_REQUEST). A reviewer agent — one of
qf.yaml review.agents, never the author — approves the current head
(MISSING_AGENT_REVIEW) with every checklist item it asks for checked — logging
only when it changes code — and its review record, a ```yaml review block
(review.v1) — when a person reviews, saying what the pull request does,
describing every test the person reviews, telling every changed design as
stories and naming the story of every requirement the person is asked about
(INCOMPLETE_CHECKLIST); every story step names a source its design has
(REVIEW_STORY_UNSOURCED).
A person reviews the pull request when classify_pull_request_tool finds it
important or risky — a requirement of criticality high or of kind security, a
trust boundary, a file that traces to nothing, a weakened test, a finding
closed without a change, or the reviewer agent's request — and always when it
changes paths.architecture_dir or the gates' own files: the CI file, the
framework pin (the submodule at paths.framework_dir, whose commit a version
move changes, and .gitmodules) and qf.yaml. Then a person approves the current
head (MISSING_PERSON_APPROVAL): seal 4, the person's review on the host, never a
file the agent could write (rules 1, 2, 7 and 14 of the quality assurance
stage). When there is something to judge, CI's checkpoint-4 review comment for
that head (post_checkpoint_review_tool) has every item answered yes
(REVIEW_ITEMS_UNANSWERED), and was not changed after the approval
(REVIEW_CHANGED_AFTER_APPROVAL). A person is an approver that is no declared
agent, no bot and not the author. After the merge, the files are not classified
again — the gates check before the merge proved them (GATES_NOT_PASSED) — so a
merged pull request needs a person for the architecture, the gates' own files,
or its review record's request and disputes.

No host setting is read (decision 6): on every push to the main branch, every
commit it adds came from a merged pull request (MERGED_WITHOUT_PULL_REQUEST)
whose final head had the approvals above and passed the gates check before the
merge (GATES_NOT_PASSED); a re-run after the merge reads an empty range, so it
proves nothing. While a release is proposed, the same holds for every commit of
the main branch since the last release, so a change that bypassed the delivery
desk blocks the release until it is accepted after the fact: an issue labelled
non-conformance names it (nonconformance.v1 found_in, or commit for a direct
push), and a person in qf.yaml urgent_approvers, not its author, comments
/accept-delivery on it (rule 12 of the quality assurance stage). A revert alone
leaves the commit in the history, so it is accepted the same way, fixed_by the
revert. The commit that started the product (the one adding qf.yaml) and those
before it are exempt.

    python gates/sup/verify_delivery_reviewed_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dataclasses import replace

from gates.sup.verify_required_checks_gate import GATES_JOB, gates_job  # noqa: E402
from tools.classify_pull_request_tool import (  # noqa: E402
    Classification,
    always,
    classify,
    headline,
    review_record,
    unsourced,
)
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.post_review_tool import checklist, required_items  # noqa: E402
from tools.read_commit_range_tool import (  # noqa: E402
    first_parents,
    is_ancestor,
    main_push,
    main_ref,
    resolve_base,
)
from tools.read_host_tool import Delivery, Host, PullRequest, delivery, read_host  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.write_release_tool import last_release, pending  # noqa: E402

GATE = "verify_delivery_reviewed_gate"
ACCEPT = "/accept-delivery"
WAY_OUT = (
    f"record it as an issue labelled non-conformance and have a person in urgent_approvers "
    f"comment {ACCEPT} on it."
)


def check(config: ProductConfig) -> list[Finding]:
    host = read_host()
    found = delivery(config.root, host)
    findings: list[Finding] = []
    if not found.on_main:
        if found.pull_request is None:
            findings.append(
                Finding(
                    "NO_PULL_REQUEST",
                    ".",
                    None,
                    f"The work on this branch has no open pull request in {found.repo}; open "
                    "one to bring it to the delivery desk.",
                )
            )
        else:
            findings += _reviewed(config, found.repo, found.pull_request)
    merged: set[int] = set()
    late: list[tuple[int | str, Finding, str | None]] = []  # after the merge, with the author
    for sha in _main_commits(config, found):
        numbers = host.pull_requests_for_commit(found.repo, sha)
        if not numbers:
            late.append(
                (
                    sha,
                    Finding(
                        "MERGED_WITHOUT_PULL_REQUEST",
                        ".",
                        None,
                        f"Commit {sha[:7]} is on the default branch of {found.repo} but came "
                        "from no merged pull request; " + WAY_OUT,
                    ),
                    None,
                )
            )
            continue
        if numbers[0] in merged:
            continue
        merged.add(numbers[0])
        pull = host.pull_request(found.repo, numbers[0])
        if pull is not None:
            for f in _reviewed(config, found.repo, pull) + _gates_passed(
                config, host, found.repo, pull
            ):
                late.append(
                    (
                        pull.number,
                        replace(f, message=f"{f.message} It is merged, so {WAY_OUT}"),
                        pull.author,
                    )
                )
    if late:
        accepted = _accepted(config, host, found.repo)
        findings += [f for what, f, author in late if not _is_accepted(accepted, what, author)]
    return findings


def _accepted(config: ProductConfig, host: Host, repo: str) -> list[tuple[dict, set[str]]]:
    """Each non-conformance's record, with the urgent approvers who accepted it."""
    found = []
    for issue in host.issues(repo, "non-conformance"):
        record, _why = issue.record("nonconformance")
        people = {c.author for c in issue.commands(ACCEPT) if c.author in config.urgent_approvers}
        if record is not None and people:
            found.append((record, people))
    return found


def _is_accepted(
    accepted: list[tuple[dict, set[str]]], what: int | str, author: str | None
) -> bool:
    """Whether a person other than the author accepted the pull request (a number)
    or the commit (a SHA)."""
    for record, people in accepted:
        if isinstance(what, int):
            named = record.get("found_in") == what
        else:
            named = what.startswith(record.get("commit") or "\0")
        if named and people - {author}:
            return True
    return False


def _main_commits(config: ProductConfig, found: Delivery) -> list[str]:
    """The commits of the main branch to check: those the push adds (the head, outside
    a push), and while a release is proposed every one since the last release."""
    root = config.root
    shas: list[str] = []
    if found.on_main:
        push = main_push()
        shas += first_parents(root, push.before) if push and push.before else [found.sha]
    if pending(config):
        main = main_ref(root) or "HEAD"
        shas += first_parents(root, last_release(root, main), main)
    start = _start(root)
    kept: list[str] = []
    for sha in shas:
        if sha and sha not in kept and not (start and is_ancestor(root, sha, start)):
            kept.append(sha)
    return kept


def _start(root) -> str | None:
    """The commit that started the product: the first to add qf.yaml."""
    run = subprocess.run(
        ["git", "-C", str(root), "log", "--diff-filter=A", "--format=%H", "--", "qf.yaml"],
        capture_output=True,
        text=True,
    )
    found = run.stdout.split() if run.returncode == 0 else []
    return found[-1] if found else None


def _reviewed(config: ProductConfig, repo: str, pull: PullRequest) -> list[Finding]:
    where = f"{repo}#{pull.number}"
    agents = set(config.review_agents)
    approvals = [r for r in pull.approvals() if r.author != pull.author]
    by_agent = [r for r in approvals if r.author in agents]
    items = required_items(config, pull.files)
    findings = []
    record = None
    if not by_agent:
        findings.append(
            Finding(
                "MISSING_AGENT_REVIEW",
                ".",
                None,
                f"{where} has no approval of its head {pull.head[:7]} from a reviewer agent "
                f"({', '.join(sorted(agents))}) other than its author: the person's watcher "
                "starts the reviewer agent (tools/watch_reviews_tool.py), or the person starts "
                "its own session for it (agent/run_reviewer_agent.md).",
            )
        )
    elif not any(_complete(r.body, items) for r in by_agent):
        checked = checklist(by_agent[-1].body) or {}
        open_items = [i for i in items if not checked.get(i)]
        findings.append(
            Finding(
                "INCOMPLETE_CHECKLIST",
                ".",
                None,
                f"The reviewer agent's approval of {where} leaves the checklist incomplete "
                f"({', '.join(open_items)}); post it with tools/post_review_tool.py.",
            )
        )
    else:
        record, why = review_record(by_agent[-1].body)
        if record is None and not pull.merged:
            findings.append(
                Finding(
                    "INCOMPLETE_CHECKLIST",
                    ".",
                    None,
                    f"The reviewer agent's approval of {where} carries no valid review record: "
                    f"{why}; post it with tools/post_review_tool.py --record.",
                )
            )
    review = person_review(config, pull, record)
    people = [r for r in approvals if r.author not in agents and not r.bot]
    if review.needed and record is not None and not pull.merged:
        gaps = _record_gaps(review, record)
        if gaps:
            findings.append(
                Finding(
                    "INCOMPLETE_CHECKLIST",
                    ".",
                    None,
                    f"The reviewer agent's review record of {where} {'; it '.join(gaps)}; post "
                    "it again with --record.",
                )
            )
    if record is not None and not pull.merged:
        findings += [
            Finding(
                "REVIEW_STORY_UNSOURCED",
                ".",
                None,
                f"The review record of {where} tells a story the design does not support: "
                f"{wrong}. Tell the design again (agent/describe_design_prompt.md).",
            )
            for wrong in unsourced(config, record.get("stories", []))
        ]
    if review.needed and not people:
        why = f" (why: {headline(review.brief)})" if review.brief else ""
        findings.append(
            Finding(
                "MISSING_PERSON_APPROVAL",
                ".",
                None,
                f"{where} needs a person's review{why}: it {'; '.join(review.reasons)}, so a "
                f"person must approve its head {pull.head[:7]} (seal 4); it waits at the "
                "delivery desk until they do.",
            )
        )
    if review.needed and record is not None:
        findings += _answers(config, repo, pull, review, record, people)
    return findings


def _record_gaps(review: Classification, record: dict) -> list[str]:
    """What a person's review needs that the reviewer agent's record leaves out."""
    gaps = []
    if not record.get("summary"):
        gaps.append("says nothing of what the pull request does (summary)")
    described = {t["file"] for t in record.get("tests", [])}
    missing = [t for t in review.tests if t not in described]
    if missing:
        gaps.append(
            f"describes no test of {', '.join(missing)}, which the person reviews "
            "(agent/describe_tests_prompt.md)"
        )
    stories = record.get("stories", [])
    untold = [d for d in review.designs if d not in {s["design"] for s in stories}]
    if untold:
        gaps.append(
            f"tells no story of the design of {', '.join(untold)} "
            "(agent/describe_design_prompt.md)"
        )
    covers = record.get("covers", {})
    asked = [u for d in review.designs for u in review.asked.get(d, []) if u not in covers]
    if asked:
        gaps.append(f"names no story for {', '.join(asked)} (covers: a story's title, or none)")
    titles = {s["story"] for s in stories}
    unknown = sorted({t for t in covers.values() if t != "none" and t not in titles})
    if unknown:
        gaps.append(f"names stories it does not tell in covers: {', '.join(unknown)}")
    return gaps


def person_review(config: ProductConfig, pull: PullRequest, record: dict | None):
    """Whether a person reviews the pull request, why and on what: classified from
    its files while it is open; once merged, from what cannot have changed."""
    if not pull.merged:
        return classify(config, pull.files, record, resolve_base(config.root))
    reasons = [r for r in [always(config, pull.files)] if r]
    if record is not None:
        base = classify(config, (), record)
        reasons += list(base.reasons)
    return Classification(tuple(reasons))


def _answers(config, repo, pull, review, record, people) -> list[Finding]:
    """The person's answers in CI's checkpoint-4 review comment for the head."""
    from tools.post_checkpoint_review_tool import answers, find_note, render

    where = f"{repo}#{pull.number}"
    expected = render(config, repo, pull, review, record)
    if expected is None or not answers(expected):  # nothing to tick: the approval is the review
        return []
    note = find_note(pull, expected)
    if note is None:
        return [
            Finding(
                "REVIEW_ITEMS_UNANSWERED",
                ".",
                None,
                f"{where} has no checkpoint-4 review comment for its head {pull.head[:7]} "
                "yet; CI posts it (tools/post_checkpoint_review_tool.py).",
            )
        ]
    open_items = [title for title, answer in answers(note.body) if answer != "yes"]
    findings = []
    if open_items:
        findings.append(
            Finding(
                "REVIEW_ITEMS_UNANSWERED",
                ".",
                None,
                f"The checkpoint-4 review of {where} has items not answered yes: "
                f"{'; '.join(open_items)}. Tick one box per item, then approve — or request "
                "changes with the reason.",
            )
        )
    stale = [r.author for r in people if r.submitted and _later(note.updated, r.submitted)]
    if people and len(stale) == len(people):
        findings.append(
            Finding(
                "REVIEW_CHANGED_AFTER_APPROVAL",
                ".",
                None,
                f"The checkpoint-4 review of {where} changed after {', '.join(stale)} approved "
                "it; approve again once the answers are as meant.",
            )
        )
    return findings


def _later(one: str, other: str) -> bool:
    from datetime import datetime

    def instant(stamp: str):
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))

    return instant(one) > instant(other)


def _gates_passed(config: ProductConfig, host: Host, repo: str, pull: PullRequest) -> list[Finding]:
    job = gates_job(config.ci_file) or GATES_JOB
    if job in host.passed_checks(repo, pull.head, before=pull.merged_at):
        return []
    return [
        Finding(
            "GATES_NOT_PASSED",
            ".",
            None,
            f"{repo}#{pull.number} was merged, but its head {pull.head[:7]} has no passing "
            f"'{job}' check from before the merge: it reached the main branch with red or "
            "unfinished gates.",
        )
    ]


def _complete(body: str, items: tuple[str, ...]) -> bool:
    checked = checklist(body)
    return checked is not None and all(checked.get(i) for i in items)


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
