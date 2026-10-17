"""Read the code host: pull requests, their reviews and checks, release tags, issues.

The framework is GitHub-native (decided 2026-07-30), so one tool reads the host,
through the GitHub REST API with the read-only token in QF_HOST_TOKEN — in CI
the token every run has (github.token, with read permissions); on a person's
machine, e.g. export QF_HOST_TOKEN=$(gh auth token). No host setting is read, so
no administrator's token is needed. With QF_HOST_FILE set, the host is read
from that JSON file instead: the tests' fake host, and a recorded host checked
offline. A host that cannot be read raises HostError, which crashes the gate:
the runner fails closed (GATE_CRASHED), never open.

The delivery is the pull request the work travels in: the one of the CI event,
else the open one of the current branch, else — on the main branch — the merged
one the head commit came from.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from tools.read_yaml_blocks_tool import yaml_blocks_in_text
from tools.validate_contract_tool import validate

__all__ = [
    "HOST_FILE",
    "HOST_TOKEN",
    "Comment",
    "Delivery",
    "FileHost",
    "GitHubHost",
    "Host",
    "HostError",
    "Issue",
    "PullRequest",
    "Review",
    "delivery",
    "host_configured",
    "read_host",
    "remote_slug",
    "repository",
]

HOST_TOKEN = "QF_HOST_TOKEN"
HOST_FILE = "QF_HOST_FILE"
API = "https://api.github.com"


class HostError(Exception):
    """The host cannot be read: no token, no repository, or the API refused."""


@dataclass(frozen=True)
class Review:
    author: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
    commit: str  # the head the review was given on
    body: str = ""
    bot: bool = False


@dataclass(frozen=True)
class PullRequest:
    number: int
    author: str
    head: str
    files: tuple[str, ...] = ()
    reviews: tuple[Review, ...] = ()
    merged: bool = False

    def approvals(self) -> list[Review]:
        """The approvals that count: each reviewer's latest decision, when it
        approves the current head."""
        latest: dict[str, Review] = {}
        for review in self.reviews:
            if review.state != "COMMENTED":
                latest[review.author] = review
        return [r for r in latest.values() if r.state == "APPROVED" and r.commit == self.head]


@dataclass(frozen=True)
class Comment:
    author: str
    body: str
    created: str  # ISO 8601


@dataclass(frozen=True)
class Issue:
    number: int
    author: str
    state: str  # open or closed
    created: str  # ISO 8601
    closed: str | None = None
    labels: tuple[str, ...] = ()
    assignees: tuple[str, ...] = ()
    body: str = ""
    comments: tuple[Comment, ...] = ()

    def record(self, tag: str) -> tuple[dict | None, str | None]:
        """The issue's one ```yaml <tag> block, checked against <tag>.v1, or None
        and why it does not count."""
        blocks = yaml_blocks_in_text(self.body, tag, Path(f"#{self.number}"))
        if len(blocks) != 1:
            return None, f"issue #{self.number} holds {len(blocks)} ```yaml {tag} blocks, not one"
        if blocks[0].error:
            return None, f"the {tag} block of #{self.number} cannot be read: {blocks[0].error}"
        violations = validate(blocks[0].data, tag)
        if violations:
            first = violations[0]
            where = first.path or "the block"
            return None, f"the {tag} block of #{self.number} breaks {tag}.v1 at '{where}': " + (
                first.message
            )
        return blocks[0].data, None

    def commands(self, command: str) -> list[Comment]:
        """The comments whose first line is the command, e.g. /confirm-fixed."""
        return [
            c for c in self.comments if (c.body.strip().splitlines() or [""])[0].strip() == command
        ]


class Host(Protocol):
    def default_branch(self, repo: str) -> str: ...
    def passed_checks(self, repo: str, sha: str) -> frozenset[str]: ...
    def pull_request(self, repo: str, number: int) -> PullRequest | None: ...
    def pull_requests_for_branch(self, repo: str, branch: str) -> list[int]: ...
    def pull_requests_for_commit(self, repo: str, sha: str) -> list[int]: ...
    def release_tags(self, repo: str) -> dict[str, str]: ...
    def issues(self, repo: str, label: str) -> list[Issue]: ...


class GitHubHost:
    def __init__(self, token: str, api: str = API):
        self.token = token
        self.api = api.rstrip("/")

    def _get(self, path: str):
        request = urllib.request.Request(
            f"{self.api}{path}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            raise HostError(f"GitHub refused {path}: HTTP {err.code}") from err
        except urllib.error.URLError as err:
            raise HostError(f"GitHub cannot be reached: {err.reason}") from err

    def _pages(self, path: str) -> list:
        joiner = "&" if "?" in path else "?"
        items, page = [], 1
        while True:
            batch = self._get(f"{path}{joiner}per_page=100&page={page}") or []
            items += batch
            if len(batch) < 100:
                return items
            page += 1

    def default_branch(self, repo: str) -> str:
        data = self._get(f"/repos/{repo}")
        if data is None:
            raise HostError(f"No repository {repo} on GitHub, or the token cannot read it.")
        return data["default_branch"]

    def passed_checks(self, repo: str, sha: str) -> frozenset[str]:
        """The names of the checks that passed on the commit (a re-run that passed counts)."""
        data = self._get(f"/repos/{repo}/commits/{sha}/check-runs?per_page=100") or {}
        runs = data.get("check_runs") or ()
        return frozenset(r["name"] for r in runs if r.get("conclusion") == "success")

    def pull_request(self, repo: str, number: int) -> PullRequest | None:
        data = self._get(f"/repos/{repo}/pulls/{number}")
        if data is None:
            return None
        files = self._pages(f"/repos/{repo}/pulls/{number}/files")
        reviews = self._pages(f"/repos/{repo}/pulls/{number}/reviews")
        return PullRequest(
            number=number,
            author=data["user"]["login"],
            head=data["head"]["sha"],
            files=tuple(f["filename"] for f in files),
            reviews=tuple(
                Review(
                    author=(r.get("user") or {}).get("login", ""),
                    state=r["state"],
                    commit=r.get("commit_id") or "",
                    body=r.get("body") or "",
                    bot=(r.get("user") or {}).get("type") == "Bot",
                )
                for r in reviews
            ),
            merged=bool(data.get("merged")),
        )

    def pull_requests_for_branch(self, repo: str, branch: str) -> list[int]:
        owner = repo.split("/")[0]
        pulls = self._get(f"/repos/{repo}/pulls?state=open&head={owner}:{branch}") or []
        return [p["number"] for p in pulls]

    def pull_requests_for_commit(self, repo: str, sha: str) -> list[int]:
        pulls = self._get(f"/repos/{repo}/commits/{sha}/pulls") or []
        return [p["number"] for p in pulls if p.get("merged_at")]

    def release_tags(self, repo: str) -> dict[str, str]:
        return {t["name"]: t["commit"]["sha"] for t in self._pages(f"/repos/{repo}/tags")}

    def issues(self, repo: str, label: str) -> list[Issue]:
        found = self._pages(f"/repos/{repo}/issues?state=all&labels={urllib.parse.quote(label)}")
        issues = []
        for i in found:
            if "pull_request" in i:  # GitHub lists pull requests as issues too
                continue
            comments = self._pages(f"/repos/{repo}/issues/{i['number']}/comments")
            issues.append(
                Issue(
                    number=i["number"],
                    author=(i.get("user") or {}).get("login", ""),
                    state=i["state"],
                    created=i["created_at"],
                    closed=i.get("closed_at"),
                    labels=tuple(lb["name"] for lb in i.get("labels") or ()),
                    assignees=tuple(a["login"] for a in i.get("assignees") or ()),
                    body=i.get("body") or "",
                    comments=tuple(
                        Comment(
                            (c.get("user") or {}).get("login", ""),
                            c.get("body") or "",
                            c["created_at"],
                        )
                        for c in comments
                    ),
                )
            )
        return issues


class FileHost:
    """A host recorded as JSON: {"repositories": {"<owner>/<name>": {...}}}."""

    def __init__(self, path: Path):
        try:
            self.data = json.loads(Path(path).read_text())["repositories"]
        except (OSError, ValueError, KeyError) as err:
            raise HostError(f"{HOST_FILE} {path} is not a readable host file: {err}") from err

    def _repo(self, repo: str) -> dict:
        if repo not in self.data:
            raise HostError(f"No repository {repo} in the host file.")
        return self.data[repo]

    def _pulls(self, repo: str) -> list[dict]:
        return self._repo(repo).get("pull_requests", [])

    def default_branch(self, repo: str) -> str:
        return self._repo(repo).get("default_branch", "main")

    def passed_checks(self, repo: str, sha: str) -> frozenset[str]:
        return frozenset(self._repo(repo).get("checks", {}).get(sha, ()))

    def pull_request(self, repo: str, number: int) -> PullRequest | None:
        for p in self._pulls(repo):
            if p["number"] == number:
                return PullRequest(
                    number=number,
                    author=p["author"],
                    head=p["head"],
                    files=tuple(p.get("files", ())),
                    reviews=tuple(Review(**r) for r in p.get("reviews", ())),
                    merged=p.get("merged", False),
                )
        return None

    def pull_requests_for_branch(self, repo: str, branch: str) -> list[int]:
        return [
            p["number"]
            for p in self._pulls(repo)
            if p.get("branch") == branch and not p.get("merged", False)
        ]

    def pull_requests_for_commit(self, repo: str, sha: str) -> list[int]:
        return [
            p["number"]
            for p in self._pulls(repo)
            if p.get("merged", False) and sha in p.get("commits", ())
        ]

    def release_tags(self, repo: str) -> dict[str, str]:
        return dict(self._repo(repo).get("tags", {}))

    def issues(self, repo: str, label: str) -> list[Issue]:
        return [
            Issue(
                number=i["number"],
                author=i["author"],
                state=i.get("state", "open"),
                created=i["created"],
                closed=i.get("closed"),
                labels=tuple(i.get("labels", ())),
                assignees=tuple(i.get("assignees", ())),
                body=i.get("body", ""),
                comments=tuple(Comment(**c) for c in i.get("comments", ())),
            )
            for i in self._repo(repo).get("issues", [])
            if label in i.get("labels", ())
        ]


def host_configured() -> bool:
    """Whether read_host can reach a host: a test host's file or a token."""
    return bool(os.environ.get(HOST_FILE) or os.environ.get(HOST_TOKEN))


def read_host() -> Host:
    if os.environ.get(HOST_FILE):
        return FileHost(Path(os.environ[HOST_FILE]))
    token = os.environ.get(HOST_TOKEN)
    if not token:
        raise HostError(
            f"No {HOST_TOKEN}: set it to a read-only GitHub token (in CI a repository "
            "secret; on your machine e.g. export QF_HOST_TOKEN=$(gh auth token))."
        )
    return GitHubHost(token, os.environ.get("GITHUB_API_URL", API))


_SLUG = re.compile(r"github\.com[:/]+([\w.-]+/[\w.-]+?)(?:\.git)?/?$")


def remote_slug(url: str) -> str | None:
    """owner/name of a GitHub remote URL (https, ssh or scp-like)."""
    found = _SLUG.search(url.strip())
    return found.group(1) if found else None


def _git(root: Path, *args: str) -> str | None:
    run = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else None


def repository(root: Path) -> str:
    """The product's repository: CI's, else the origin remote's."""
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    slug = remote_slug(_git(root, "remote", "get-url", "origin") or "")
    if slug is None:
        raise HostError("The product has no GitHub origin remote, so its host is unknown.")
    return slug


@dataclass(frozen=True)
class Delivery:
    repo: str
    pull_request: PullRequest | None
    on_main: bool  # the head is on the default branch: the work was merged
    sha: str


def _event_number() -> int | None:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not Path(path).is_file():
        return None
    try:
        event = json.loads(Path(path).read_text())
    except ValueError:
        return None
    return (event.get("pull_request") or {}).get("number")


def delivery(root: Path, host: Host) -> Delivery:
    repo = repository(root)
    sha = _git(root, "rev-parse", "HEAD") or ""
    number = _event_number()
    if number is not None:
        return Delivery(repo, host.pull_request(repo, number), False, sha)
    branch = os.environ.get("GITHUB_REF_NAME") or _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch not in ("HEAD", host.default_branch(repo)):
        numbers = host.pull_requests_for_branch(repo, branch)
        found = host.pull_request(repo, numbers[0]) if numbers else None
        return Delivery(repo, found, False, sha)
    numbers = host.pull_requests_for_commit(repo, sha)
    found = host.pull_request(repo, numbers[0]) if numbers else None
    return Delivery(repo, found, True, sha)
