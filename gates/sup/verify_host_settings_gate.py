"""verify_host_settings_gate — SUP.1 BP1, SWE.1 BP6, SWE.2 BP5, SWE.3 BP5: every delivery reviewed.

The work travels in a pull request (NO_PULL_REQUEST; on the default branch, a
commit with no merged pull request is MERGED_WITHOUT_PULL_REQUEST). A reviewer
agent — one of qf.yaml review.agents, never the author — approves the current
head (MISSING_AGENT_REVIEW) with every checklist item checked
(INCOMPLETE_CHECKLIST). Every pull request that changes paths.architecture_dir,
and every one whose number is a multiple of review.sample_every, also has a
person's approval of the current head (MISSING_PERSON_APPROVAL): seal 4, the
person's review on the host, never a file the agent could write (decisions 1, 2
and 7 of the quality assurance stage). A person is an approver that is no
declared agent, no bot and not the author.

    python gates/sup/verify_host_settings_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.post_review_tool import CHECKLIST, checklist  # noqa: E402
from tools.read_host_tool import PullRequest, delivery, read_host  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "verify_host_settings_gate"


def check(config: ProductConfig) -> list[Finding]:
    found = delivery(config.root, read_host())
    pull = found.pull_request
    if pull is None:
        if found.on_main:
            return [
                Finding(
                    "MERGED_WITHOUT_PULL_REQUEST",
                    ".",
                    None,
                    f"Commit {found.sha[:7]} is on the default branch of {found.repo} but came "
                    "from no merged pull request; every change arrives as a reviewed delivery.",
                )
            ]
        return [
            Finding(
                "NO_PULL_REQUEST",
                ".",
                None,
                f"The work on this branch has no open pull request in {found.repo}; open one "
                "to bring it to the delivery desk.",
            )
        ]
    where = f"{found.repo}#{pull.number}"
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


def sampled(config: ProductConfig, pull: PullRequest) -> str | None:
    """Why a person must review the pull request, or None."""
    architecture = config.relative(config.architecture_dir).rstrip("/") + "/"
    if any(f.startswith(architecture) for f in pull.files):
        return f"changes the architecture ({architecture})"
    if pull.number % config.sample_every == 0:
        return f"is in the sample (1 in {config.sample_every}, by number)"
    return None


def _complete(body: str) -> bool:
    items = checklist(body)
    return items is not None and all(items.get(i) for i in CHECKLIST)


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
