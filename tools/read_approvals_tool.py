"""Read checkpoint decisions: which files an approval covers, and whether it counts.

A decision is approval.v1 in <approvals_dir>/<date>-checkpoint-<n>-<subject>.yaml.
The latest file for a checkpoint and subject counts. It is current only while it
approves, and every file it covers is unchanged and no file was added or
removed — so editing approved work withdraws the approval. The customer's
decision on a release (checkpoint 5) is due only while a release is proposed,
and covers its release record and its validation record.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tools.read_product_config_tool import ProductConfig
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file
from tools.validate_contract_tool import validate
from tools.write_release_tool import pending

__all__ = ["ApprovalState", "approval_state", "checkpoint_due", "sha256", "subject_files"]


@dataclass(frozen=True)
class ApprovalState:
    """status: approved, missing, changes_requested, outdated or invalid."""

    status: str
    reason: str
    path: Path | None = None
    date: datetime | None = None


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def subject_files(config: ProductConfig, approves: str) -> list[Path]:
    """The files a checkpoint's approval covers, sorted by repository path."""
    if approves == "diagrams":
        directory = config.diagrams_dir
        files = [
            *directory.glob("*.json"),
            *directory.glob("*.invariants.yaml"),
            *directory.glob("*.wishes.yaml"),
        ]
    elif approves == "requirements":
        files = [*config.requirements_dir.rglob("*.md"), config.glossary_file]
    elif approves == "stack":
        files = [config.stack_file, *_decision_record(config)]
    elif approves == "release":
        files = [
            folder / f"{version}.yaml"
            for version in pending(config)
            for folder in (config.releases_dir, config.validation_records_dir)
        ]
    else:
        raise ValueError(f"the files approved as '{approves}' are not defined yet")
    return sorted((f for f in files if f.is_file()), key=config.relative)


def checkpoint_due(config: ProductConfig, approves: str) -> bool:
    """Whether a checkpoint's decision is needed now: the customer's decision on
    a release only while one is proposed (decision 10 of the validation stage)."""
    return approves != "release" or bool(pending(config))


def _decision_record(config: ProductConfig) -> list[Path]:
    """The stack's decision record, as the stack file names it, if it can be read."""
    try:
        data = read_yaml_file(config.stack_file)
    except (OSError, YamlReadError):
        return []
    record = data.get("decision_record") if isinstance(data, dict) else None
    return [config.root / record] if isinstance(record, str) else []


def approval_state(config: ProductConfig, checkpoint: int, approves: str) -> ApprovalState:
    """Whether the latest decision at a checkpoint is an approval that still counts."""
    pattern = f"*-checkpoint-{checkpoint}-{approves}.yaml"
    folder = config.approvals_dir
    candidates = sorted(folder.glob(pattern)) if folder.is_dir() else []
    if not candidates:
        return ApprovalState("missing", f"no checkpoint-{checkpoint} decision is recorded")
    latest = candidates[-1]
    shown = config.relative(latest)
    try:
        data = read_yaml_file(latest)
    except YamlReadError as err:
        return ApprovalState("invalid", f"{shown} cannot be read: {err.message}", latest)
    if validate(data, "approval"):
        return ApprovalState("invalid", f"{shown} is not a valid approval", latest)
    date = datetime.fromisoformat(data["date"].replace("Z", "+00:00"))
    if data["decision"] != "approved":
        return ApprovalState(
            "changes_requested", f"changes requested: {data.get('comment', '')}", latest, date
        )
    recorded = {s["path"]: s["sha256"] for s in data["subject"]}
    current = {config.relative(f): sha256(f) for f in subject_files(config, approves)}
    if recorded != current:
        paths = sorted({p for p, _ in set(recorded.items()) ^ set(current.items())})
        return ApprovalState(
            "outdated", f"files changed since the approval: {', '.join(paths)}", latest, date
        )
    return ApprovalState("approved", "approved", latest, date)
