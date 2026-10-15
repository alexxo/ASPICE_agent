"""verify_delivery_reviewed_gate — SUP.1 BP1, SWE.1 BP6, SWE.2 BP5, SWE.3 BP5: deliveries reviewed.

The work travels in a pull request (NO_PULL_REQUEST). A reviewer agent — one of
qf.yaml review.agents, never the author — approves the current head
(MISSING_AGENT_REVIEW) with every checklist item checked (INCOMPLETE_CHECKLIST).
Every pull request that changes paths.architecture_dir or the gates' own files
— the CI file, the framework pin (.gitmodules) and qf.yaml — and every one whose
number is a multiple of review.sample_every, also has a person's approval of
the current head (MISSING_PERSON_APPROVAL): seal 4, the person's review on the
host, never a file the agent could write (decisions 1, 2 and 7 of the quality
assurance stage). A person is an approver that is no declared agent, no bot and
not the author.

No host setting is read (decision 6): on every push to the main branch, every
commit it adds came from a merged pull request (MERGED_WITHOUT_PULL_REQUEST)
whose final head had the approvals above and passed the gates check
(GATES_NOT_PASSED). While a release is proposed, the same holds for every
commit of the main branch since the last release, so a change that bypassed
the delivery desk blocks the release until it is reverted or reviewed. The
commit that started the product (the one adding qf.yaml) and those before it
are exempt.

    python gates/sup/verify_delivery_reviewed_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gates.sup.verify_required_checks_gate import GATES_JOB, gates_job  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.post_review_tool import CHECKLIST, checklist  # noqa: E402
from tools.read_commit_range_tool import (  # noqa: E402
    first_parents,
    is_ancestor,
    main_push,
    main_ref,
)
from tools.read_host_tool import Delivery, Host, PullRequest, delivery, read_host  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.write_release_tool import last_release, pending  # noqa: E402

GATE = "verify_delivery_reviewed_gate"


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
    for sha in _main_commits(config, found):
        numbers = host.pull_requests_for_commit(found.repo, sha)
        if not numbers:
            findings.append(
                Finding(
                    "MERGED_WITHOUT_PULL_REQUEST",
                    ".",
                    None,
                    f"Commit {sha[:7]} is on the default branch of {found.repo} but came from "
                    "no merged pull request; revert it, or bring it back through a reviewed "
                    "pull request.",
                )
            )
            continue
        if numbers[0] in merged:
            continue
        merged.add(numbers[0])
        pull = host.pull_request(found.repo, numbers[0])
        if pull is not None:
            findings += _reviewed(config, found.repo, pull)
            findings += _gates_passed(config, host, found.repo, pull)
    return findings


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
    findings = []
    if not by_agent:
        findings.append(
            Finding(
                "MISSING_AGENT_REVIEW",
                ".",
                None,
                f"{where} has no approval of its head {pull.head[:7]} from a reviewer agent "
                f"({', '.join(sorted(agents))}) other than its author.",
            )
        )
    elif not any(_complete(r.body) for r in by_agent):
        items = checklist(by_agent[-1].body) or {}
        open_items = [i for i in CHECKLIST if not items.get(i)]
        findings.append(
            Finding(
                "INCOMPLETE_CHECKLIST",
                ".",
                None,
                f"The reviewer agent's approval of {where} leaves the checklist incomplete "
                f"({', '.join(open_items)}); post it with tools/post_review_tool.py.",
            )
        )
    why = sampled(config, pull)
    people = [r for r in approvals if r.author not in agents and not r.bot]
    if why and not people:
        findings.append(
            Finding(
                "MISSING_PERSON_APPROVAL",
                ".",
                None,
                f"{where} {why}, so a person must approve its head {pull.head[:7]} (seal 4); "
                "it waits at the delivery desk until they do.",
            )
        )
    return findings


def _gates_passed(config: ProductConfig, host: Host, repo: str, pull: PullRequest) -> list[Finding]:
    job = gates_job(config.ci_file) or GATES_JOB
    if job in host.passed_checks(repo, pull.head):
        return []
    return [
        Finding(
            "GATES_NOT_PASSED",
            ".",
            None,
            f"{repo}#{pull.number} was merged, but its head {pull.head[:7]} has no passing "
            f"'{job}' check: it reached the main branch with red or unfinished gates.",
        )
    ]


def sampled(config: ProductConfig, pull: PullRequest) -> str | None:
    """Why a person must review the pull request, or None."""
    architecture = config.relative(config.architecture_dir).rstrip("/") + "/"
    if any(f.startswith(architecture) for f in pull.files):
        return f"changes the architecture ({architecture})"
    guarded = {config.relative(config.ci_file), ".gitmodules", "qf.yaml"}
    touched = sorted(guarded & set(pull.files))
    if touched:
        return f"changes the gates' own files ({', '.join(touched)})"
    if pull.number % config.sample_every == 0:
        return f"is in the sample (1 in {config.sample_every}, by number)"
    return None


def _complete(body: str) -> bool:
    items = checklist(body)
    return items is not None and all(items.get(i) for i in CHECKLIST)


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
