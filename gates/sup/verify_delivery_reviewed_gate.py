"""verify_delivery_reviewed_gate — SUP.1 BP1, SWE.1 BP6, SWE.2 BP5, SWE.3 BP5: deliveries reviewed.

The work travels in a pull request (NO_PULL_REQUEST). A reviewer agent — one of
qf.yaml review.agents, never the author — approves the current head
(MISSING_AGENT_REVIEW; when it requested changes on that head, the finding
says so) with every checklist item it asks for checked — logging
only when it changes code — and its review record, a ```yaml review block
(review.v1) — telling every changed design as stories; when a person reviews,
saying what the pull request does; with the results, describing their
software-level tests; at each gap it approves, what the build does there now,
from lines the product has, and what follows for the user
(INCOMPLETE_CHECKLIST); every story step names a source
its design has (REVIEW_STORY_UNSOURCED); with the results, it lists the cases
expected of each criterion of the requirements proved, from the criteria alone,
each with its test — a case no test checks only with a person asked
(REVIEW_EXPECTED_CASES_MISSING).
A person reviews the pull request when classify_pull_request_tool calls one:
for the results of software verification, on the pull request that brings
them (checkpoint 4); for a question of what is wanted — a gap a story marks
that the reviewer agent approved, a weakened test, a finding closed without a
change, the reviewer agent's request, a change of qf.yaml or .gitmodules; and
always for the architecture. Then a person approves the current head
(MISSING_PERSON_APPROVAL): seal 4, the person's review on the host, never a
file the agent could write (rules 1, 2, 7 and 14 of the quality assurance
stage). When there is something to judge, CI's checkpoint-4 review comment for
that head (post_checkpoint_review_tool) exists — for the results, once the
tree's verification report is written — has every item answered yes
(REVIEW_ITEMS_UNANSWERED), and was not changed after the approval
(REVIEW_CHANGED_AFTER_APPROVAL). A person is an approver that is no declared
agent, no bot and not the author. After the merge, the files are not classified
again — the gates check before the merge proved them (GATES_NOT_PASSED) — so a
merged pull request needs a person for the architecture, the product's
settings, or its review record's request and disputes.

A checkpoint decision (checkpoints 1, 2, 3 and 5) is given on the host: a
pull request from branch checkpoint/<n> waits until qf.yaml review.architect
approves its head (MISSING_PERSON_APPROVAL), and the latest merge of every
checkpoint the history holds — the record the approval gates read — merged a
head the architect approved on that pull request (UNAPPROVED_MERGE). A merge
without it counts once a later pull request of that checkpoint is approved and
merged: revert, and bring the work again.

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
from tools.post_merge_status_tool import CHANGES_REQUESTED  # noqa: E402
from tools.post_review_tool import checklist, required_items  # noqa: E402
from tools.read_approvals_tool import checkpoint_merges, checkpoint_of  # noqa: E402
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
    findings += _checkpoints(config, host, found.repo)
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


def _changes_requested(pull: PullRequest, agents: set[str]) -> list[str]:
    """The reviewer agents whose latest decision requests changes on the head."""
    latest = {}
    for review in pull.reviews:
        if review.author in agents and review.state != "COMMENTED":
            latest[review.author] = review
    return sorted(
        a for a, r in latest.items() if r.state == "CHANGES_REQUESTED" and r.commit == pull.head
    )


def _start(root) -> str | None:
    """The commit that started the product: the first to add qf.yaml."""
    run = subprocess.run(
        ["git", "-C", str(root), "log", "--diff-filter=A", "--format=%H", "--", "qf.yaml"],
        capture_output=True,
        text=True,
    )
    found = run.stdout.split() if run.returncode == 0 else []
    return found[-1] if found else None


def _checkpoints(config: ProductConfig, host: Host, repo: str) -> list[Finding]:
    """The latest merge of each checkpoint merged a head the architect approved."""
    latest = {m.checkpoint: m for m in checkpoint_merges(config.root)}
    architect = config.review_architect
    findings = []
    for n, merge in sorted(latest.items()):
        pull = host.pull_request(repo, merge.number)
        approvers = {r.author for r in pull.approvals()} if pull else set()
        if pull is not None and pull.head == merge.head and architect in approvers:
            continue
        findings.append(
            Finding(
                "UNAPPROVED_MERGE",
                ".",
                None,
                f"Checkpoint {n}: #{merge.number} was merged ({merge.commit[:7]}) without "
                f"{architect}'s approval of its head {merge.head[:7]}. Revert the merge, bring "
                f"the work again from branch checkpoint/{n} and let the agent merge it once "
                f"{architect} approved (agent/record_checkpoint_tool.py).",
            )
        )
    return findings


def _reviewed(config: ProductConfig, repo: str, pull: PullRequest) -> list[Finding]:
    where = f"{repo}#{pull.number}"
    agents = set(config.review_agents)
    approvals = [r for r in pull.approvals() if r.author != pull.author]
    by_agent = [r for r in approvals if r.author in agents]
    items = required_items(config, pull.files)
    findings = []
    record = None
    sent_back = _changes_requested(pull, agents)
    if not by_agent and sent_back:
        findings.append(
            Finding(
                "MISSING_AGENT_REVIEW",
                ".",
                None,
                f"{where}: {CHANGES_REQUESTED} on its head {pull.head[:7]} "
                f"({', '.join(sent_back)}): fix the findings of its review — its body and its "
                "line comments — and push; the watcher reviews the new head.",
            )
        )
    elif not by_agent:
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
    if record is not None and not pull.merged:
        gaps = _record_gaps(review, record, config.root)
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
        findings += _expected_findings(review, record, where)
    checkpoint = checkpoint_of(pull.branch)
    if (
        checkpoint is not None
        and not pull.merged
        and config.review_architect not in {r.author for r in people}
    ):
        behalf = f" on behalf of {config.customer}" if checkpoint == 5 else ""
        findings.append(
            Finding(
                "MISSING_PERSON_APPROVAL",
                ".",
                None,
                f"{where} needs {config.review_architect}'s decision (why: checkpoint "
                f"{checkpoint}): they approve its head {pull.head[:7]}{behalf}, or request "
                "changes with the reason; it waits at the delivery desk until they do.",
            )
        )
    elif review.needed and not people:
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


def _record_gaps(review: Classification, record: dict, root: Path) -> list[str]:
    """What the reviewer agent's record leaves out: the stories of every changed
    design; when a person reviews, the summary; with the results, the
    descriptions of their tests; at each gap it approved, what the build does
    there now, from lines the product has."""
    gaps = []
    if review.needed and not record.get("summary"):
        gaps.append("says nothing of what the pull request does (summary)")
    described = {t["file"] for t in record.get("tests", [])}
    missing = [t for t in review.tests if t not in described] if review.proves else []
    if missing:
        gaps.append(
            f"describes no test of {', '.join(missing)}, which the person reads with the results "
            "(agent/describe_tests_prompt.md)"
        )
    told = {s["design"] for s in record.get("stories", [])}
    untold = [d for d in review.designs if d not in told]
    if untold:
        gaps.append(
            f"tells no story of the design of {', '.join(untold)} "
            "(agent/describe_design_prompt.md)"
        )
    now = {(g["design"], g["story"], g["step"]): g for g in record.get("gaps", [])}
    for design, story, step in review.gaps:
        if (design, story, step) not in now:
            gaps.append(f"does not say what the build does now at the gap “{step}” (gaps)")
    for told in now.values():
        unknown = [s for s in told["source"] if not _line_exists(root, s)]
        if unknown:
            gaps.append(
                f"names lines the product does not have for the gap “{told['step']}”: "
                f"{', '.join(unknown)}"
            )
    return gaps


def _line_exists(root: Path, source: str) -> bool:
    """Whether path:line names a line of a file under the product's root."""
    path, _, line = source.rpartition(":")
    file = (root / path).resolve()
    if not file.is_file() or not file.is_relative_to(root.resolve()):
        return False
    with file.open(errors="replace") as text:
        return sum(1 for _ in text) >= int(line)


def _expected_findings(review: Classification, record: dict, where: str) -> list[Finding]:
    """With the results: the expected cases of every requirement proved, each with a
    test, unless the reviewer agent asks a person about it (agent/expect_cases_prompt.md)."""
    if not review.proves:
        return []
    cases = record.get("expected", [])
    findings = []
    listed = {c["requirement"] for c in cases}
    unlisted = [u for u in review.proves if u not in listed]
    if unlisted:
        findings.append(
            Finding(
                "REVIEW_EXPECTED_CASES_MISSING",
                ".",
                None,
                f"The review record of {where} lists no expected case of {', '.join(unlisted)}, "
                "which it proves: list them from the criteria alone "
                "(agent/expect_cases_prompt.md) and give each its test.",
            )
        )
    untested = [c for c in cases if c["test"] == "missing"]
    if untested and record.get("person") == "none":
        first = untested[0]
        findings.append(
            Finding(
                "REVIEW_EXPECTED_CASES_MISSING",
                ".",
                None,
                f"The review record of {where} approves {len(untested)} expected case(s) no test "
                f"checks, e.g. {first['requirement']} criterion {first['criterion']}: "
                f"{first['case']}. A missing case is a finding for the tester; a case held wrong "
                "is a question for a person (condition 2).",
            )
        )
    return findings


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
    if expected is None:
        return [
            Finding(
                "REVIEW_ITEMS_UNANSWERED",
                ".",
                None,
                f"{where} brings the results, but this tree has no verification report yet; CI "
                "writes it (tools/write_verification_report_tool.py) before the results are "
                "posted.",
            )
        ]
    if not answers(expected):  # nothing to tick: the approval alone is the review
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
