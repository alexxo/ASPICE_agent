"""Read the commits a pull request adds, and the files each one changes.

The history gates read only the commits not yet on the main branch, base..HEAD
(decision 9): older commits were proven when their pull request merged. The
base is the one CI passes (--base, or the environment variable QF_BASE);
without one it is the merge base with the remote's default branch, else with a
local main or master, else with the remote's main or master. When none of these
exists the whole history is read.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

__all__ = [
    "GITMODULES",
    "Change",
    "Commit",
    "Push",
    "branch",
    "commits",
    "file_at",
    "files_at",
    "gitlink",
    "first_parents",
    "is_ancestor",
    "issue_mentions",
    "main_push",
    "main_ref",
    "reached_main",
    "resolve_base",
    "submodule_url",
    "uncommitted",
]

GITMODULES = ".gitmodules"


@dataclass(frozen=True)
class Change:
    status: str  # A added, M modified, D deleted, R renamed (path is the new path)
    path: str  # repository-relative, posix


@dataclass(frozen=True)
class Commit:
    sha: str
    changes: tuple[Change, ...]

    @property
    def short(self) -> str:
        return self.sha[:7]


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )


def _merge_base(root: Path, ref: str) -> str | None:
    run = _git(root, "merge-base", ref, "HEAD")
    if run.returncode != 0:
        return None
    return run.stdout.strip() or None


def main_ref(root: Path) -> str | None:
    """The main branch as this checkout knows it: the remote's default branch,
    else a local main or master, else the remote's (a CI checkout has only those)."""
    default = _git(root, "rev-parse", "--abbrev-ref", "origin/HEAD")
    candidates = [default.stdout.strip()] if default.returncode == 0 else []
    for ref in [*candidates, "main", "master", "origin/main", "origin/master"]:
        if ref and _git(root, "rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return ref
    return None


_ISSUE = re.compile(r"#([0-9]+)\b")


def issue_mentions(root: Path, span: str) -> dict[int, list[datetime]]:
    """Every issue number a commit message of span names (#<n>), with the dates
    of the commits naming it, oldest first; span is a revision or a range."""
    run = _git(root, "log", "--reverse", "--format=%cI%x00%B%x01", span, "--")
    found: dict[int, list[datetime]] = {}
    for entry in run.stdout.split("\x01") if run.returncode == 0 else []:
        if "\x00" not in entry:
            continue
        stamp, message = entry.strip("\n").split("\x00", 1)
        for number in dict.fromkeys(int(n) for n in _ISSUE.findall(message)):
            found.setdefault(number, []).append(datetime.fromisoformat(stamp))
    return found


def reached_main(root: Path, text: str) -> datetime | None:
    """When text first reached the main branch: the date of the oldest commit
    on its first-parent line — the merge, for a pull request — whose change adds
    it; None while it is not there."""
    ref = main_ref(root)
    if ref is None:
        return None
    run = _git(
        root, "log", ref, "--first-parent", "--diff-merges=first-parent", "-S", text,
        "--reverse", "--format=%cI",
    )  # fmt: skip
    dates = run.stdout.split() if run.returncode == 0 else []
    return datetime.fromisoformat(dates[0]) if dates else None


def resolve_base(root: Path, base: str | None = None) -> str | None:
    """The commit the range starts after, or None to read the whole history."""
    wanted = base or os.environ.get("QF_BASE") or None
    if wanted:
        return _merge_base(root, wanted)
    ref = main_ref(root)
    return _merge_base(root, ref) if ref else None


@dataclass(frozen=True)
class Push:
    """A push to the main branch, as CI's event names it."""

    before: str | None  # the main branch before the push; None for its first push
    after: str


def main_push() -> Push | None:
    """The push to the default branch this CI run is for, or None (a pull request,
    another branch, or no CI event)."""
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.isfile(path):
        return None
    try:
        event = json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError:
        return None
    default = (event.get("repository") or {}).get("default_branch")
    if not default or event.get("ref") != f"refs/heads/{default}":
        return None
    before = event.get("before") or ""
    return Push(None if set(before) <= {"0"} else before, event.get("after") or "")


def is_ancestor(root: Path, older: str, newer: str) -> bool:
    """Whether older is in newer's history (False when older is not in the clone)."""
    return _git(root, "merge-base", "--is-ancestor", older, newer).returncode == 0


def first_parents(root: Path, base: str | None, tip: str = "HEAD") -> list[str]:
    """The commits of the main line from base (excluded) to tip, oldest first:
    a merge commit stands for the pull request it merged."""
    span = f"{base}..{tip}" if base else tip
    run = _git(root, "rev-list", "--first-parent", "--reverse", span)
    return run.stdout.split() if run.returncode == 0 else []


def branch(root: Path) -> str | None:
    """The branch the work is on: the pull request's head branch in CI
    (GITHUB_HEAD_REF), else the checked-out branch; None when detached."""
    if os.environ.get("GITHUB_HEAD_REF"):
        return os.environ["GITHUB_HEAD_REF"]
    run = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    name = run.stdout.strip() if run.returncode == 0 else ""
    return name if name and name != "HEAD" else None


def commits(root: Path, base: str | None) -> list[Commit]:
    """The commits of base..HEAD, oldest first, each with the files it changes."""
    span = f"{base}..HEAD" if base else "HEAD"
    run = _git(root, "rev-list", "--reverse", span)
    if run.returncode != 0:
        return []
    return [Commit(sha, _changes(root, sha)) for sha in run.stdout.split()]


def _changes(root: Path, sha: str) -> tuple[Change, ...]:
    run = _git(root, "diff-tree", "--no-commit-id", "-r", "-M", "--name-status", "--root", sha)
    changes = []
    for line in run.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changes.append(Change(parts[0][0], parts[-1]))
    return tuple(changes)


def file_at(root: Path, rev: str, path: str) -> str | None:
    """The text of a file at a revision, or None when it does not exist there."""
    run = _git(root, "show", f"{rev}:{path}")
    return run.stdout if run.returncode == 0 else None


def files_at(root: Path, rev: str) -> list[str]:
    """Every file of a revision's tree, repository-relative."""
    run = _git(root, "ls-tree", "-r", "--name-only", rev)
    return run.stdout.splitlines() if run.returncode == 0 else []


def uncommitted(root: Path) -> list[str]:
    """Files changed or added in the working tree but not committed."""
    run = _git(root, "status", "--porcelain", "--untracked-files=all")
    return [line[3:].split(" -> ")[-1] for line in run.stdout.splitlines() if len(line) > 3]


def gitlink(root: Path, rev: str, path: str) -> str | None:
    """The commit a revision pins the submodule at path to, or None."""
    entry = _git(root, "ls-tree", rev, "--", path).stdout.strip()
    mode, _, rest = entry.partition(" ")
    return rest.split()[1] if mode == "160000" else None


def submodule_url(root: Path, path: str) -> str | None:
    """The URL .gitmodules records for the submodule at path, or None."""
    if not (Path(root) / GITMODULES).is_file():
        return None
    run = _git(root, "config", "-f", GITMODULES, "--get-regexp", r"^submodule\..*\.path$")
    for line in run.stdout.splitlines():
        key, _, value = line.partition(" ")
        if value.strip().rstrip("/") == path:
            name = key[len("submodule.") : -len(".path")]
            url = _git(root, "config", "-f", GITMODULES, f"submodule.{name}.url")
            return url.stdout.strip() or None
    return None
