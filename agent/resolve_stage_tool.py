"""Which stage is the product in? Worked out from what is on disk, every time.

The stages of agent/stages.yaml are walked in order. A stage is done when its
implemented gates pass and, if it closes with a checkpoint, the latest decision
there is an approval that still matches the files; a stage without a closing
checkpoint is done only once its stage done record exists (stage_done.v1,
written by record_stage_done_tool when its gates first pass). A stage whose
checkpoint sits in the middle (stage 3: the stack is approved before components
are designed) runs its gates_after_checkpoint only once that approval is current.
The first stage that is not done is the current one. There is no state file: the
agent can stop and resume at any time. Once every stage of the flow is done, the
gates of every built event stage run too (decision 4 of the problem resolution
stage), so their rules hold on every pull request.

What fails (findings) and what is only reported (reported), § 5 What CI fails on:
- the always-on gates, on every change whatever the stage; those that read the
  code host run only where one is configured;
- every finished stage: a checkpoint approved once, or a stage done record —
  breaking its work fails;
- a missing seal 4 or 5: a pull request waiting for a person's approval, a
  release waiting for the customer's decision.
The current stage, never finished, is work in progress (status in_progress): its
findings are reported and enforced where it ends — at its checkpoint and at the
release: while a release is proposed, every stage is enforced. Every gate not
run is listed under not_run with its reason: stage_not_reached, planned, or
no_host.

    python agent/resolve_stage_tool.py [--root PRODUCT] [--check]

With --check — the product CI's command — the exit code is 1 when there are
findings, or the configuration is invalid.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from functools import partial
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.read_stages_tool import (  # noqa: E402
    Stage,
    always_gates,
    flow_stages,
    host_gates,
    read_stages,
)
from agent.record_checkpoint_tool import current_approval  # noqa: E402
from agent.run_gates_tool import passed, run_gates  # noqa: E402
from tools.read_approvals_tool import (  # noqa: E402
    checkpoint_due,
    ever_approved,
    stage_done_record,
)
from tools.read_host_tool import host_configured  # noqa: E402
from tools.read_product_config_tool import (  # noqa: E402
    ConfigError,
    ProductConfig,
    read_product_config,
)
from tools.write_release_tool import pending  # noqa: E402

__all__ = ["CUSTOMER_DECISION", "HOST_APPROVAL", "needs_record", "resolve_stage"]

HOST_APPROVAL = "MISSING_PERSON_APPROVAL"  # verify_delivery_reviewed_gate: seal 4 not given yet
# the person's review of seal 4 not answered, or changed after their approval: still seal 4
PERSON_REVIEW = {HOST_APPROVAL, "REVIEW_ITEMS_UNANSWERED", "REVIEW_CHANGED_AFTER_APPROVAL"}
CUSTOMER_DECISION = "MISSING_CUSTOMER_DECISION"  # verify_release_evidence_gate: seal 5 not yet
SEALS = PERSON_REVIEW | {CUSTOMER_DECISION}


def resolve_stage(root: Path) -> dict:
    root = Path(root)
    try:
        config = read_product_config(root)
    except ConfigError as err:
        return {
            "stage": None,
            "status": "invalid_config",
            "reason": err.message,
            "findings": [asdict(err.to_finding())],
            "reported": [],
            "done": [],
            "not_run": [],
        }
    reachable = host_configured()
    always = [g for g in always_gates() if reachable or g not in host_gates()]
    skipped = [{"gate": g, "reason": "no_host"} for g in always_gates() if g not in always]
    state = _walk(config, root)
    state["not_run"] = skipped + state["not_run"]
    findings = [f for r in run_gates(root, always) for f in r["findings"]]
    if not findings:
        return state
    rules = {f["rule"] for f in findings}
    if rules and rules <= PERSON_REVIEW and state["status"] != "gates_failing":
        status, why = "awaiting_checkpoint", "a person's review of the pull request on the host"
    else:
        status, why = "gates_failing", f"{len(findings)} finding(s) of the always-on gates"
    return {
        **state,
        "status": status,
        "reason": f"{why}; {state['reason']}",
        "findings": findings + state["findings"],
    }


def needs_record(s: Stage) -> bool:
    """A stage whose last work is not closed by a recorded checkpoint."""
    return s.checkpoint is None or s.checkpoint_on_host or bool(s.gates_after_checkpoint)


def _walk(config: ProductConfig, root: Path) -> dict:
    done: list[str] = []
    flow = flow_stages()
    releasing = bool(pending(config))  # no release while any finding remains
    for index, s in enumerate(flow):
        stop = partial(_stop, s, flow[: index + 1], [*flow[index + 1 :], *_events()], done)
        if s.gates:
            results = run_gates(root, s.gates)
            if not passed(results):
                finished = releasing or _approved_once(config, s) or _recorded(config, s)
                return _failing(s, _flat(results), finished, stop, s.gates_after_checkpoint)
        approved, why = True, ""
        if s.checkpoint and not s.checkpoint_on_host and checkpoint_due(config, s.approves):
            approval, why = current_approval(config, s.checkpoint, s.approves)
            approved = approval is not None
        if s.checkpoint and not approved:
            status = "awaiting_checkpoint" if s.implemented else "not_implemented"
            reason = f"checkpoint {s.checkpoint}: {why}"
            return stop(status, reason, skipped=s.gates_after_checkpoint)
        if s.gates_after_checkpoint:
            results = run_gates(root, s.gates_after_checkpoint)
            if not passed(results):
                return _failing(s, _flat(results), releasing or _recorded(config, s), stop)
        if not s.implemented:  # never done, whether or not its checkpoint is due
            return stop("not_implemented", "this stage is not built yet")
        if needs_record(s) and not _recorded(config, s):
            return stop(
                "in_progress",
                "the stage's gates pass; record it as done: "
                f"python agent/record_stage_done_tool.py --stage {s.id}",
            )
        done = [*done, s.id]
    planned = _not_run([*flow, *_events()], [], ())
    for s in _events():
        results = run_gates(root, s.gates)
        if not passed(results):
            findings = _flat(results)
            return {
                "stage": s.id,
                "number": s.number,
                "process": s.process,
                "done": done,
                "status": "gates_failing",
                "findings": findings,
                "reported": [],
                "reason": f"{len(findings)} finding(s) of the {s.id.replace('_', ' ')} rules",
                "not_run": planned,
            }
    return {
        "stage": None,
        "status": "complete",
        "done": done,
        "findings": [],
        "reported": [],
        "not_run": planned,
        "reason": "every stage in the flow is done",
    }


def _stop(s, walked, ahead, done, status, reason, findings=(), reported=(), skipped=()) -> dict:
    """The resolver's answer when the walk stops at stage s."""
    return {
        "stage": s.id,
        "number": s.number,
        "process": s.process,
        "done": done,
        "status": status,
        "reason": reason,
        "findings": list(findings),
        "reported": list(reported),
        "not_run": _not_run(walked, ahead, skipped),
    }


def _failing(s: Stage, findings: list[dict], finished: bool, stop, skipped=()) -> dict:
    """A stage's failing gates: enforced once it was finished, else reported."""
    waiting = _awaited(s, {f["rule"] for f in findings})
    if waiting:
        return stop(
            "awaiting_checkpoint", f"checkpoint {s.checkpoint}: {waiting}", findings, (), skipped
        )
    if finished:
        reason = f"{len(findings)} finding(s) in a finished stage"
        return stop("gates_failing", reason, findings, (), skipped)
    seals = [f for f in findings if f["rule"] in SEALS]
    rest = [f for f in findings if f["rule"] not in SEALS]
    reason = f"{len(rest)} finding(s) reported: the stage is in progress"
    return stop("in_progress", reason, seals, rest, skipped)


def _approved_once(config: ProductConfig, s: Stage) -> bool:
    """The work before a recorded checkpoint is finished once it was approved."""
    if not s.checkpoint or s.checkpoint_on_host:
        return False
    return ever_approved(config, s.checkpoint, s.approves)


def _recorded(config: ProductConfig, s: Stage) -> bool:
    return needs_record(s) and stage_done_record(config, s.id, s.number) is not None


def _events() -> list[Stage]:
    return [s for s in read_stages() if s.trigger == "event" and s.implemented]


def _flat(results: list[dict]) -> list[dict]:
    return [f for r in results for f in r["findings"]]


def _not_run(walked, ahead, skipped) -> list[dict]:
    """Every gate not run: planned ones, and those of stages not reached."""
    entries = [{"gate": g, "reason": "stage_not_reached"} for g in skipped]
    for s in walked:
        entries += [{"gate": g, "reason": "planned"} for g in s.planned_gates]
    for s in ahead:
        entries += [{"gate": g, "reason": "stage_not_reached"} for g in s.built_gates]
        entries += [{"gate": g, "reason": "planned"} for g in s.planned_gates]
    seen: set[str] = set()
    unique = []
    for entry in entries:
        if entry["gate"] not in seen:
            seen.add(entry["gate"])
            unique.append(entry)
    return unique


def _awaited(s, rules: set[str]) -> str | None:
    """What the stage waits for when the only finding is the customer's decision on
    the release (seal 5), checked by a gate so CI blocks the merge. Seal 4, a
    person's review on the host, is an always-on gate's finding."""
    if s.checkpoint and not s.checkpoint_on_host and rules == {CUSTOMER_DECISION}:
        return "the customer's decision on the release"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true", help="exit 1 when reached gates fail")
    args = parser.parse_args(argv)
    state = resolve_stage(args.root)
    print(json.dumps(state, indent=2))
    if args.check and state["findings"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
