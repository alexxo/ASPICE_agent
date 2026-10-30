"""Read checkpoint decisions: which files an approval covers, and whether it counts.

The person decides on the code host (v4.0.0): the work of checkpoint <n> travels
in a pull request from branch checkpoint/<n>, qf.yaml review.architect approves
its head, and the agent merges it with a merge commit (record_checkpoint_tool).
That merge commit is the record — GitHub's "Merge pull request #<number> from
<owner>/checkpoint/<n>", its second parent the approved head — so a decision is
read from git history alone, and verify_delivery_reviewed_gate checks every such
merge against the host (UNAPPROVED_MERGE). The latest merge of a checkpoint
counts. It is current only while every file it covers is what the approved head
holds — so editing approved work withdraws the approval. The customer's
decision on a release (checkpoint 5), given by the architect on their behalf, is
due only while a release is proposed, and covers its release record and its
validation record.

Whether a stage was finished once is read here too: a checkpoint approved at
least once, or a stage done record (stage_done.v1) in
<approvals_dir>/<date>-stage-<n>-done.yaml for a stage without a closing
checkpoint.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tools.read_product_config_tool import ProductConfig
from tools.read_requirements_tool import changed_since
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file
from tools.validate_contract_tool import validate
from tools.write_release_tool import pending

__all__ = [
    "ApprovalState",
    "Merge",
    "approval_state",
    "changed_files",
    "checkpoint_due",
    "checkpoint_merges",
    "checkpoint_of",
    "ever_approved",
    "previous_approval",
    "sha256",
    "stage_done_record",
    "subject_files",
]

BRANCH = re.compile(r"^checkpoint/([1-9][0-9]*)$")
# GitHub's subject of a merge commit: the pull request's number and its head branch
MERGED = re.compile(r"^Merge pull request #([0-9]+) from \S+?/(checkpoint/[1-9][0-9]*)$")


@dataclass(frozen=True)
class Merge:
    """A checkpoint's pull request, merged: the approval as git history holds it."""

    checkpoint: int
    number: int  # the pull request
    commit: str  # the merge commit
    head: str  # the approved head: the merge commit's second parent
    date: datetime  # when it was merged


@dataclass(frozen=True)
class ApprovalState:
    """status: approved, missing or outdated."""

    status: str
    reason: str
    merge: Merge | None = None

    @property
    def date(self) -> datetime | None:
        return self.merge.date if self.merge else None


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checkpoint_of(branch: str) -> int | None:
    """The checkpoint a pull request's head branch brings, e.g. 2 for checkpoint/2."""
    found = BRANCH.match(branch)
    return int(found.group(1)) if found else None


def checkpoint_merges(root: Path, checkpoint: int | None = None) -> list[Merge]:
    """The merged pull requests of a checkpoint (of every one, without checkpoint)
    the head's history holds, oldest first: in the order of the history, never of
    the clock."""
    run = _git(root, "log", "--merges", "--topo-order", "--format=%H %P %cI%x00%s", "HEAD")
    merges = []
    for line in run.splitlines() if run else []:
        ids, _, subject = line.partition("\0")
        found = MERGED.match(subject.strip())
        parts = ids.split()
        if found is None or len(parts) != 4:
            continue
        number = checkpoint_of(found.group(2))
        if checkpoint is None or number == checkpoint:
            date = datetime.fromisoformat(parts[3].replace("Z", "+00:00"))
            merges.append(Merge(number, int(found.group(1)), parts[0], parts[2], date))
    return merges[::-1]


def changed_files(config: ProductConfig, approves: str, commit: str) -> list[str]:
    """The files a checkpoint's approval covers whose content is not what commit
    holds — added since included, by repository path."""
    paths = [config.relative(f) for f in subject_files(config, approves)]
    if not paths:
        return []
    listed = _git(config.root, "ls-tree", "-r", commit, "--", *paths) or ""
    held = {}
    for line in listed.splitlines():
        meta, _, path = line.partition("\t")
        held[path] = meta.split()[2]
    now = (_git(config.root, "hash-object", "--", *paths) or "").split()
    if len(now) != len(paths):
        return paths  # git cannot read them: nothing shows they are unchanged
    return [p for p, blob in zip(paths, now, strict=True) if held.get(p) != blob]


def _git(root: Path, *args: str) -> str | None:
    run = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else None


def subject_files(config: ProductConfig, approves: str) -> list[Path]:
    """The files a checkpoint's approval covers, sorted by repository path."""
    if approves == "diagrams":
        files = [
            *_diagram_files(config),
            *(spec.with_suffix(".html") for spec in config.diagrams_dir.glob("*.json")),
            config.diagrams_dir / "review.html",
        ]  # with the pictures and the page the person saw
    elif approves == "requirements":
        files = [
            *config.requirements_dir.rglob("*.md"),
            config.glossary_file,
            config.requirements_dir / "review.html",
            config.requirements_dir / "questions.yaml",  # the answers the page shows
            *_diagram_files(config),  # what they are derived from: a changed diagram withdraws it
        ]
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


def _diagram_files(config: ProductConfig) -> list[Path]:
    directory = config.diagrams_dir
    return [
        *directory.glob("*.json"),
        *directory.glob("*.invariants.yaml"),
        *directory.glob("*.wishes.yaml"),
    ]


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
    """Whether the latest merged pull request of a checkpoint is an approval that
    still covers the files."""
    merges = checkpoint_merges(config.root, checkpoint)
    if not merges:
        return ApprovalState(
            "missing", f"no pull request from branch checkpoint/{checkpoint} is merged"
        )
    latest = merges[-1]
    changed = changed_files(config, approves, latest.head)
    if changed:
        return ApprovalState(
            "outdated",
            f"files changed since #{latest.number} was approved: {', '.join(changed)}",
            latest,
        )
    return ApprovalState("approved", f"approved in #{latest.number}", latest)


def ever_approved(config: ProductConfig, checkpoint: int, approves: str) -> bool:
    """Whether any pull request of the checkpoint was merged, even one outdated since."""
    return bool(checkpoint_merges(config.root, checkpoint))


def previous_approval(config: ProductConfig, checkpoint: int, approves: str) -> Merge | None:
    """The latest approval of other content than the files hold now, review pages
    left out: what a review page marks its changes against."""
    for merge in reversed(checkpoint_merges(config.root, checkpoint)):
        if any(not p.endswith(".html") for p in changed_files(config, approves, merge.head)):
            return merge
    return None


def stage_done_record(config: ProductConfig, stage_id: str, number: int) -> Path | None:
    """The first valid stage done record of the stage, if one exists."""
    folder = config.approvals_dir
    for path in sorted(folder.glob(f"*-stage-{number}-done.yaml")) if folder.is_dir() else []:
        try:
            data = read_yaml_file(path)
        except YamlReadError:
            continue
        if not validate(data, "stage_done") and data["stage"] == stage_id:
            return path
    return None


def latest_stage_done(config: ProductConfig, stage_id: str, number: int) -> dict | None:
    """The latest valid stage done record of the stage, if one exists."""
    folder = config.approvals_dir
    found = None
    for path in sorted(folder.glob(f"*-stage-{number}-done.yaml")) if folder.is_dir() else []:
        try:
            data = read_yaml_file(path)
        except YamlReadError:
            continue
        if not validate(data, "stage_done") and data["stage"] == stage_id:
            found = data
    return found


def requirements_changed(config: ProductConfig, stage_id: str, number: int) -> list[str]:
    """The requirements added or changed since the stage's latest stage done record
    — what a stage built from the requirements (stages 4 to 7) is not done for yet.
    None changed when there is no record, or git cannot show its commit."""
    record = latest_stage_done(config, stage_id, number)
    if record is None:
        return []
    return changed_since(config, record["commit"]) or []
