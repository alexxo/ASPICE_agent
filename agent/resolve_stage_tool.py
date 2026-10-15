"""Which stage is the product in? Worked out from what is on disk, every time.

The stages of agent/stages.yaml are walked in order. A stage is done when its
implemented gates pass and, if it closes with a checkpoint, the latest decision
there is an approval that still matches the files. A stage whose checkpoint sits
in the middle (stage 3: the stack is approved before components are designed)
runs its gates_after_checkpoint only once that approval is current. A checkpoint on the
host (seal 4: a person's review of the pull request) is checked by the stage's gates; while
the only finding left is that approval, the stage awaits its checkpoint; so does seal 5,
whose missing decision verify_release_evidence_gate reports while a release is proposed,
and which is due only then. The first stage that is not done is the current one. There is
no state file: the agent can stop and resume at any time. Once every stage of the flow is
done, the gates of every built event stage run too (decision 4 of the problem resolution
stage), so their rules hold on every pull request.

Planned gates are not run and are listed under not_run, so a stage that is done
only as far as the built gates can tell is never presented as fully checked.

    python agent/resolve_stage_tool.py [--root PRODUCT] [--check]

With --check — the product CI's command — the exit code is 1 when the gates of a
stage the product has reached fail, or the configuration is invalid; a stage
waiting for a recorded checkpoint or not built yet does not fail CI, but a pull
request waiting for its person's approval does: it must not merge before it.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.read_stages_tool import flow_stages, read_stages  # noqa: E402
from agent.record_checkpoint_tool import current_approval  # noqa: E402
from agent.run_gates_tool import passed, run_gates  # noqa: E402
from tools.read_approvals_tool import checkpoint_due  # noqa: E402
from tools.read_product_config_tool import ConfigError, read_product_config  # noqa: E402

__all__ = ["CUSTOMER_DECISION", "HOST_APPROVAL", "resolve_stage"]

HOST_APPROVAL = "MISSING_PERSON_APPROVAL"  # verify_delivery_reviewed_gate: seal 4 not given yet
CUSTOMER_DECISION = "MISSING_CUSTOMER_DECISION"  # verify_release_evidence_gate: seal 5 not yet


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
            "done": [],
            "not_run": [],
        }
    done: list[str] = []
    not_run: list[str] = []
    for s in flow_stages():
        not_run.extend(g for g in s.planned_gates if g not in not_run)
        state = {"stage": s.id, "number": s.number, "process": s.process, "done": done}
        if s.gates:
            results = run_gates(root, s.gates)
            if not passed(results):
                findings = [f for r in results for f in r["findings"]]
                waiting = _awaited(s, {f["rule"] for f in findings})
                if waiting:
                    return {
                        **state,
                        "status": "awaiting_checkpoint",
                        "findings": findings,
                        "not_run": not_run,
                        "reason": f"checkpoint {s.checkpoint}: {waiting}",
                    }
                return {
                    **state,
                    "status": "gates_failing",
                    "findings": findings,
                    "reason": f"{len(findings)} finding(s)",
                    "not_run": not_run,
                }
        approved = True
        if s.checkpoint and not s.checkpoint_on_host and checkpoint_due(config, s.approves):
            approval, why = current_approval(config, s.checkpoint, s.approves)
            approved = approval is not None
        if s.checkpoint and not approved:
            status = "awaiting_checkpoint" if s.implemented else "not_implemented"
            return {
                **state,
                "status": status,
                "findings": [],
                "not_run": not_run,
                "reason": f"checkpoint {s.checkpoint}: {why}",
            }
        if s.gates_after_checkpoint:
            results = run_gates(root, s.gates_after_checkpoint)
            if not passed(results):
                findings = [f for r in results for f in r["findings"]]
                return {
                    **state,
                    "status": "gates_failing",
                    "findings": findings,
                    "reason": f"{len(findings)} finding(s) after checkpoint {s.checkpoint}",
                    "not_run": not_run,
                }
        if not s.implemented:  # never done, whether or not its checkpoint is due
            return {
                **state,
                "status": "not_implemented",
                "findings": [],
                "not_run": not_run,
                "reason": "this stage is not built yet",
            }
        done = [*done, s.id]
    for s in read_stages():
        if s.trigger != "event" or not s.implemented:
            continue
        results = run_gates(root, s.gates)
        if not passed(results):
            findings = [f for r in results for f in r["findings"]]
            return {
                "stage": s.id,
                "number": s.number,
                "process": s.process,
                "done": done,
                "status": "gates_failing",
                "findings": findings,
                "reason": f"{len(findings)} finding(s) of the {s.id.replace('_', ' ')} rules",
                "not_run": not_run,
            }
    return {
        "stage": None,
        "status": "complete",
        "done": done,
        "findings": [],
        "not_run": not_run,
        "reason": "every stage in the flow is done",
    }


def _awaited(s, rules: set[str]) -> str | None:
    """What the stage waits for when the only finding is its seal's missing
    approval, checked by a gate so CI blocks the merge: a person's review on the
    host (seal 4), the customer's decision on the release (seal 5)."""
    if s.checkpoint_on_host and rules == {HOST_APPROVAL}:
        return "a person's approval of the pull request on the host"
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
