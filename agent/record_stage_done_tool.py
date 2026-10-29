"""Record that a stage without a closing checkpoint is done: its gates passed.

The record is stage_done.v1 in <approvals_dir>/<date>-stage-<n>-done.yaml, with
the commit the gates passed on. It is written only for the current stage, once
its gates pass (and its checkpoint, if one sits in the middle, is approved);
from then on the stage is finished and enforced (§ 5 What CI fails on): the first
record says the stage was finished once. A stage built from the requirements
(stages 4 to 7) is recorded again after requirements were added or changed
since its latest record (FB-63); the new record names them. The detailed design
is recorded again only once each of them is served by a decision record dated
since then — decided by the person, and accepted, when the requirement is
critical (criticality high, or kind security); by the agent otherwise.

    python agent/record_stage_done_tool.py --stage ID|NUMBER [--root PRODUCT]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from agent.read_stages_tool import UnknownStage, stage  # noqa: E402
from agent.record_checkpoint_tool import current_approval  # noqa: E402
from agent.render_decisions_tool import read_decisions  # noqa: E402
from agent.resolve_stage_tool import needs_record, resolve_stage  # noqa: E402
from agent.run_gates_tool import passed, reached_gates, run_gates  # noqa: E402
from tools.read_approvals_tool import latest_stage_done, requirements_changed  # noqa: E402
from tools.read_product_config_tool import read_product_config  # noqa: E402
from tools.read_requirements_tool import critical, read_requirements  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

__all__ = ["record_stage_done"]


def record_stage_done(root: Path, stage_id: str, now: datetime | None = None) -> Path:
    root = Path(root)
    s = stage(stage_id)
    if not needs_record(s):
        raise ValueError(
            f"stage {s.number} {s.id} closes with checkpoint {s.checkpoint}: its approval "
            "records it, with record_checkpoint_tool"
        )
    state = resolve_stage(root)
    if state["stage"] != s.id:
        raise ValueError(
            f"stage {s.number} {s.id} is not the current stage: the product is at "
            f"{state['stage']} ({state['status']}: {state['reason']})"
        )
    config = read_product_config(root)
    if s.checkpoint and not s.checkpoint_on_host:
        approval, why = current_approval(config, s.checkpoint, s.approves)
        if approval is None:
            raise ValueError(f"stage {s.number} {s.id} awaits checkpoint {s.checkpoint}: {why}")
    if not passed(run_gates(root, reached_gates(root, s))):
        raise ValueError(f"stage {s.number} {s.id} is not done: its gates still fail")
    changed = requirements_changed(config, s.id, s.number) if s.built_from_requirements else []
    if changed and s.id == "detailed_design":
        undecided = _undecided(config, changed, latest_stage_done(config, s.id, s.number))
        if undecided:
            raise ValueError(
                f"stage {s.number} {s.id} is not done for the changed requirements: "
                f"{'; '.join(undecided)}"
            )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    if commit.returncode != 0:
        raise ValueError(f"{root} has no commit to record: {commit.stderr.strip()}")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    data = {
        "stage": s.id,
        "number": s.number,
        "date": now.isoformat(timespec="seconds"),
        "commit": commit.stdout.strip(),
    }
    if changed:
        data["requirements_changed"] = changed
    violations = validate(data, "stage_done")
    if violations:
        first = violations[0]
        raise ValueError(f"not a valid record at '{first.path or 'the record'}': {first.message}")
    config.approvals_dir.mkdir(parents=True, exist_ok=True)
    path = config.approvals_dir / f"{now:%Y-%m-%dT%H%M%SZ}-stage-{s.number}-done.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _undecided(config, changed: list[str], previous: dict) -> list[str]:
    """Each changed requirement no decision record since the previous record serves
    as it must: the person's, accepted, for a critical one; anyone's otherwise."""
    since = previous["date"][:10]
    requirements = {r.text("uid"): r.data for r in read_requirements(config) if r.text("uid")}
    decisions = [
        data
        for _, data in read_decisions(config).values()
        if "decided_by" in data and data["date"] >= since and data["status"] != "superseded"
    ]
    missing = []
    for uid in changed:
        serving = [d for d in decisions if uid in d.get("requirements", [])]
        if critical(requirements.get(uid, {})):
            if not any(d["decided_by"] == "person" and d["status"] == "accepted" for d in serving):
                missing.append(
                    f"{uid} is critical: the person decides — a decision record decided_by "
                    "person, answered with agent/render_decisions_tool.py --ask"
                )
        elif not serving:
            missing.append(f"{uid}: no decision record serves it (decided_by agent)")
    return missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--stage", required=True)
    args = parser.parse_args(argv)
    try:
        path = record_stage_done(args.root, args.stage)
    except UnknownStage as err:
        print(str(err), file=sys.stderr)
        return 2
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
