"""Start the reviewer agent on its own: one fresh session per new pull request head.

The person starts the watcher once a working day, in a terminal of their own
with the reviewer agent's token in QF_HOST_TOKEN — never the author's session
(rule 1 of the quality assurance stage). It watches the product's open pull
requests and, for every head the reviewer agent has not reviewed yet whose
crossing sign waits for it (qf/merge: "the reviewer agent's approval"), starts
a fresh reviewer session following agent/run_reviewer_agent.md: this product
only, one session at a time, every head once. The session runs with the
reviewer's tools only — reading, the host, its own tools and its review
record's folder; no edit of the work, no commit, no push (--command replaces
the agent command, {prompt} standing for the prompt; that agent's settings
must then prevent any change). The session runs in a copy of the pull
request's head of its own, a git worktree the watcher makes at
.qf/reviews/<n>-<sha>/, never in the author's folder, where the author and the
framework go on working. A reviewer never changes the work: whatever the
agent, the watcher compares that copy's commit and changed files (.qf/ left
out) before and after each session, and on any change shows the banner
REVIEWER CHANGED THE WORK, keeps the copy, and pauses every review until the
person types R. After a review the session's records go to the product's
.qf/reviews/ and the copy is removed; a stopped review keeps it.

Before each review it describes, for the person's review, the tests a person
would review (agent/describe_tests_prompt.md) and tells the changed designs as
stories (agent/describe_design_prompt.md), each in a session that sees those
files only, in a temporary folder outside the product, without the token; the
results go to .qf/reviews/<n>-<sha>.tests.yaml and .stories.yaml, and the
reviewer copies them into its record unchanged.

Every event is one line with the time, and so is every change of a pull
request's state, naming who acts next: waits for CI, gates red (the author
fixes them), waits for a review by the people of qf.yaml review.people with
the address where they act, ready to merge — and a warning when a head
has no crossing sign after 10 minutes, since CI may not run at all.

A session that ends without a review —
the reviewer stopped, asked a question, the token was refused, or the session
ran out of time (20 minutes, a limit for a stuck session; a line every 5
minutes says a review is still running) — is shown as a banner: why, what to
do, and the session's log (.qf/reviews/<n>-<sha>.log), in red where the
terminal shows colour (NO_COLOR switches it off), with a desktop notification
where the system has one. The
watcher goes on with the other pull requests; a stopped head is not retried on
its own: type R and Enter to review the stopped heads again. Ctrl+C ends it
with the day's summary, the heads still stopped listed again.

    QF_HOST_TOKEN="$(cat ~/.aspice_agent_reviewer_bot_token/<owner>)" \\
        python .framework/tools/watch_reviews_tool.py --root .

The token is given to the watcher alone, for its life: the terminal never
holds it (PowerShell: QUICKSTART step 9).
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.read_host_tool import HOST_TOKEN, Host, HostError, read_host, repository  # noqa: E402
from tools.read_product_config_tool import (  # noqa: E402
    ConfigError,
    ProductConfig,
    read_product_config,
)

__all__ = ["Stop", "Watcher", "banner", "claude_command", "due", "tools", "waits_for_person"]

WAITS_FOR_REVIEWER = "the reviewer agent's approval"
WAITS_FOR_PERSON = ("a review by ", "a person's review")  # post_merge_status_tool's words
NO_SIGN_AFTER = 10 * 60  # seconds a head may go without a crossing sign before a warning
LOGS = Path(".qf/reviews")
WIDTH = 72
TIMEOUT = 20 * 60  # seconds one review session may take: a limit for a stuck one
PROGRESS = 5 * 60  # seconds between the lines saying a review is still running
# The reviewer's tools: reading, the host, the framework's own commands, its
# record's folder — never an edit of the work, a commit or a push.
READ_ONLY = (
    "Read",
    "Grep",
    "Glob",
    "Write(.qf/reviews/**)",
    "Bash(git fetch:*)",
    "Bash(git worktree:*)",
    "Bash(git log:*)",
    "Bash(git diff:*)",
    "Bash(git show:*)",
    "Bash(gh api:*)",
    "Bash(gh pr view:*)",
    "Bash(gh pr diff:*)",
    "Bash(claude -p:*)",
)
FRAMEWORK_COMMANDS = (
    "agent/read_config_tool.py",
    "agent/load_skills_tool.py",
    "tools/classify_pull_request_tool.py",
    "tools/post_review_tool.py",
)


def tools(framework: str) -> tuple[str, ...]:
    """The reviewer session's allowed tools, the framework at its path in the product."""
    commands = [
        f"Bash({python} {framework}/{tool}:*)"
        for tool in FRAMEWORK_COMMANDS
        for python in ("python", "python3")
    ]
    return (*READ_ONLY, *commands)


@dataclass(frozen=True)
class Stop:
    """A review session that ended without a review."""

    number: int
    head: str
    why: str
    do: str
    log: str
    title: str = "REVIEW STOPPED"


def banner(stop: Stop, colour: bool = False) -> str:
    """The stopped review, impossible to miss: why, what to do, where the log is."""
    rule = "#" * WIDTH
    lines = [rule, f"#  {stop.title}: pull request #{stop.number}, head {stop.head[:7]}", "#"]
    for label, text in (("Why:", stop.why), ("Do:", stop.do)):
        lines += _wrapped(label, text)
        lines.append("#")
    lines += [f"#  Log:   {stop.log}", rule]
    text = "\n".join(lines)
    return f"\033[1;31m{text}\033[0m" if colour else text


def _wrapped(label: str, text: str) -> list[str]:
    import textwrap

    width = WIDTH - 11
    body = textwrap.wrap(" ".join(text.split()), width) or [""]
    first = f"#  {label:<6} {body[0]}"
    return [first] + [f"#         {line}" for line in body[1:]]


def waits_for_person(sign: str) -> bool:
    """Whether the crossing sign waits for a person's review."""
    return any(words in sign for words in WAITS_FOR_PERSON)


def due(host: Host, repo: str, agents: set[str], done: set[tuple[int, str]]) -> list[tuple]:
    """The heads to review now: open, the crossing sign waiting for the reviewer
    agent, no review of that head by it yet, and not tried in this run."""
    found = []
    for number in host.open_pull_requests(repo):
        pull = host.pull_request(repo, number)
        if pull is None or (number, pull.head) in done:
            continue
        if any(r.author in agents and r.commit == pull.head for r in pull.reviews):
            continue
        sign = host.merge_sign(repo, pull.head) or ""
        if WAITS_FOR_REVIEWER in sign:
            found.append((number, pull.head))
    return found


def _prompt(
    config: ProductConfig,
    repo: str,
    number: int,
    described: dict[str, str] | None = None,
    copy: Path | None = None,
) -> str:
    framework = config.framework_dir.resolve().as_posix()
    described = described or {}
    here = (
        f" You are in a copy of the pull request's head the watcher made, {copy}: review "
        "there and make no copy of your own; write your record under .qf/reviews/ of this "
        f"folder. The product is {config.root.resolve()}."
        if copy is not None
        else ""
    )
    tests = (
        f" The tests a person would review are described already, in {described['tests']}: if "
        "your record needs tests, put that list under `tests` as it is; never describe a test "
        "yourself."
        if "tests" in described
        else ""
    )
    stories = (
        f" The changed designs are told as stories already, in {described['stories']}: if your "
        "record needs stories, put that list under `stories` as it is; never write or change a "
        "story yourself."
        if "stories" in described
        else ""
    )
    return (
        f"Follow {framework}/agent/run_reviewer_agent.md for pull request #{number} of {repo}."
        f"{here}{tests}{stories} You run unattended: if you must stop or ask, do not wait for an "
        "answer — end "
        "with one line starting 'STOPPED:' saying why, and one starting 'DO:' saying what the "
        "person does."
    )


def _describe_prompt(config: ProductConfig, files: list[str], what: str = "tests") -> str:
    """The describe instructions themselves, so the session needs no file but the
    tests, or the designs."""
    name = "describe_tests_prompt.md" if what == "tests" else "describe_design_prompt.md"
    rules = (Path(__file__).resolve().parents[1] / "agent" / name).read_text()
    rules = rules.split("## You", 1)[-1]
    task = "Describe the tests of" if what == "tests" else "Tell as stories the designs of"
    return (
        f"{task} these files, which are all this folder holds: "
        f"{' '.join(files)}. Read nothing else.\n\n## You{rules}"
    )


def claude_command(framework: str):
    """The default agent: Claude Code, unattended, with the reviewer's tools only."""

    def command(prompt: str) -> list[str]:
        return ["claude", "-p", prompt, "--allowedTools", ",".join(tools(framework))]

    return command


def claude_describe_command(prompt: str) -> list[str]:
    """The describe session: Claude Code, reading only, in a folder of tests or
    designs only."""
    return ["claude", "-p", prompt, "--allowedTools", "Read"]


@dataclass
class Watcher:
    config: ProductConfig
    host: Host
    repo: str
    command: object = None  # prompt -> argv
    describe: object = None  # prompt -> argv, for the describe sessions; None: none
    out: object = print
    colour: bool = False
    notify: object = None
    done: set = field(default_factory=set)
    stopped: dict = field(default_factory=dict)  # (number, head) -> Stop
    reviews: int = 0
    timeout: int = TIMEOUT
    progress: int = PROGRESS
    clock: object = time.monotonic
    shown: dict = field(default_factory=dict)  # number -> (head, the state last shown)
    unsigned: dict = field(default_factory=dict)  # (number, head) -> when first seen unsigned
    paused: bool = False  # a reviewer changed the work: no review until the person types R
    copy: object = None  # (root, number, head, folder) -> bool; None: a git worktree of the head

    def say(self, text: str) -> None:
        self.out(f"{datetime.now():%H:%M}  {text}")

    def once(self) -> None:
        agents = set(self.config.review_agents)
        for number, head in [] if self.paused else due(self.host, self.repo, agents, self.done):
            if self.paused:
                break
            self.done.add((number, head))
            self.review(number, head)
        for number in self.host.open_pull_requests(self.repo):
            pull = self.host.pull_request(self.repo, number)
            if pull is not None:
                reviewed = any(r.author in agents and r.commit == pull.head for r in pull.reviews)
                sign = self.host.merge_sign(self.repo, pull.head)
                self.report(number, pull.head, sign, reviewed, pull)

    def report(self, number: int, head: str, sign: str | None, reviewed: bool, pull=None) -> None:
        """One line when a pull request's state changes, naming who acts next."""
        state = self.state(number, head, sign, reviewed, pull)
        if state is None or self.shown.get(number) == (head, state):
            return
        self.shown[number] = (head, state)
        self.say(f"#{number} head {head[:7]}: {state}")

    def state(
        self, number: int, head: str, sign: str | None, reviewed: bool, pull=None
    ) -> str | None:
        if sign is None:
            first = self.unsigned.setdefault((number, head), self.clock())
            if self.clock() - first >= NO_SIGN_AFTER:
                return f"no crossing sign after {NO_SIGN_AFTER // 60} min: check that CI runs"
            return None
        if sign == "Ready to merge":
            return "ready to merge; the agent merges"
        if "gates running" in sign:
            return "waits for CI (gates running)"
        if "gates red" in sign:
            gates = sign.split("gates red", 1)[1].lstrip(": ").strip() or "see CI"
            return f"gates red ({gates}): the author fixes them, no review yet"
        if WAITS_FOR_REVIEWER in sign:
            started = reviewed or (number, head) in self.done  # its own line, or a banner
            return None if started else "waits for the reviewer agent"
        if waits_for_person(sign):
            people = " or ".join(self.config.review_people) or "a person"
            return f"waits for a review by {people}: {self.address(number, pull)}"
        return None

    def address(self, number: int, pull) -> str:
        """Where the person acts: CI's checkpoint-4 comment, else the changes,
        where Review changes → Approve is."""
        from tools.post_checkpoint_review_tool import MARK

        page = f"https://github.com/{self.repo}/pull/{number}"
        notes = [n for n in (pull.notes if pull else ()) if n.bot and MARK in n.body]
        return f"{page}#issuecomment-{notes[-1].id}" if notes else f"{page}/files"

    def review(self, number: int, head: str) -> None:
        self.say(f"#{number} head {head[:7]}: review started")
        log = LOGS / f"{number}-{head[:7]}.log"
        (self.config.root / LOGS).mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "GH_TOKEN": os.environ.get(HOST_TOKEN, "")}  # gh posts as reviewer
        described, failed = self.describe_work(number, head)
        if failed is not None:
            self.stopped[(number, head)] = failed
            self.out(banner(failed, self.colour))
            if self.notify:
                self.notify(f"Review stopped: #{number}", failed.why)
            return
        copy = self.config.root / LOGS / f"{number}-{head[:7]}"
        if not (self.copy or _copy_head)(self.config.root, number, head, copy):
            stop = Stop(
                number,
                head,
                "The pull request's head could not be fetched into a copy of the reviewer's "
                "own.",
                "Check that the product folder reaches its origin (git fetch), then type R and "
                "Enter to review this head again.",
                log.as_posix(),
            )
            self.stopped[(number, head)] = stop
            self.out(banner(stop, self.colour))
            if self.notify:
                self.notify(f"Review stopped: #{number}", stop.why)
            return
        before = folder_state(copy)
        described = {k: str(self.config.root / v) for k, v in described.items()}
        try:
            output, timed_out = self._run(number, head, env, described, copy)
        except OSError as err:
            output, timed_out = f"The agent could not be started: {err}", False
        (self.config.root / log).write_text(output)
        self.reviews += 1
        _keep_records(copy, self.config.root / LOGS)
        changed = _changes(before, folder_state(copy))
        if changed:
            self.paused = True
            stop = Stop(
                number,
                head,
                f"The reviewer's copy of the head changed during the review: {changed}. A "
                "reviewer never changes the work, and the agent's settings must prevent it "
                "(Claude Code: the watcher's allowed tools).",
                f"Verify your LLM settings; the copy is kept, to see the change, at "
                f"{copy.relative_to(self.config.root).as_posix()}. Reviews are paused: type R "
                "to resume.",
                log.as_posix(),
                "REVIEWER CHANGED THE WORK",
            )
            self.stopped[(number, head)] = stop
            self.out(banner(stop, self.colour))
            if self.notify:
                self.notify(f"Reviewer changed the work: #{number}", stop.why)
            return
        pull = self.host.pull_request(self.repo, number)
        agents = set(self.config.review_agents)
        posted = [r for r in (pull.reviews if pull else ()) if r.author in agents]
        posted = [r for r in posted if r.commit == head]
        if posted:
            _remove_copy(self.config.root, copy)
            self.say(f"#{number} head {head[:7]}: {_outcome(posted[-1].state)}")
            self.stopped.pop((number, head), None)
            return
        stop = _stop(number, head, output, timed_out, log.as_posix(), self.timeout)
        self.stopped[(number, head)] = stop
        self.out(banner(stop, self.colour))
        if self.notify:
            self.notify(f"Review stopped: #{number}", stop.why)

    def describe_work(self, number: int, head: str) -> tuple[dict[str, str], Stop | None]:
        """The tests a person would review, described, and the changed designs, told
        as stories — each in a session that sees those files alone: the head is
        unpacked from the host, the files are copied into an otherwise empty
        folder, and the session runs there, without the reviewer's token. Returns
        each result's file by kind (tests, stories), or why one failed; nothing to
        describe gives neither. The folders are temporary ones outside the product,
        and the instructions come in the prompt, so no session has a path to the
        requirements."""
        if self.describe is None:
            return {}, None
        import shutil as _shutil

        tree = self.config.root / LOGS / f"{number}-head"
        env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", HOST_TOKEN)}
        try:
            _shutil.rmtree(tree, ignore_errors=True)
            if not _unpack(self.config.root, number, head, tree):
                return {}, None  # no copy of the head: the reviewer describes them itself
            from tools.classify_pull_request_tool import classify

            config = read_product_config(tree)
            pull = self.host.pull_request(self.repo, number)
            found = classify(config, pull.files if pull else ())
            design_dir = config.relative(config.detailed_design_dir).rstrip("/")
            designs = [
                f"{design_dir}/{d}{suffix}"
                for d in found.designs
                for suffix in (".md", ".sequence.json")
                if (tree / design_dir / f"{d}{suffix}").is_file()
            ]
            described: dict[str, str] = {}
            for what, files in (("tests", list(found.candidates)), ("stories", designs)):
                if not files:
                    continue
                kept, stop = self._describe(number, head, env, tree, config, what, files)
                if stop is not None:
                    return {}, stop
                described[what] = kept
            return described, None
        except (ConfigError, OSError) as err:
            return {}, Stop(
                number,
                head,
                f"The work could not be described: {err}",
                "Read the log, then type R and Enter to review this head again.",
                (LOGS / f"{number}-{head[:7]}.log").as_posix(),
            )
        finally:
            _shutil.rmtree(tree, ignore_errors=True)

    def _describe(self, number, head, env, tree, config, what, files) -> tuple[str, Stop | None]:
        """One describe session in a folder of these files only; its checked
        result's file, or why it failed."""
        import shutil as _shutil
        import tempfile

        import yaml

        alone = Path(tempfile.mkdtemp(prefix="qf-describe-"))  # outside the product
        log = LOGS / f"{number}-{head[:7]}.{what}.log"
        try:
            for name in files:
                target = alone / name
                target.parent.mkdir(parents=True, exist_ok=True)
                _shutil.copyfile(tree / name, target)
            output, timed_out = self._session(
                self.describe(_describe_prompt(self.config, files, what)), alone, env, number, head
            )
        finally:
            _shutil.rmtree(alone, ignore_errors=True)
        (self.config.root / log).write_text(output)
        if what == "tests":
            entries, why = _descriptions(output, files)
        else:
            entries, why = _stories(output, config, files)
        if timed_out or entries is None:
            failed = (
                "The tests could not be described: "
                if what == "tests"
                else ("The designs could not be told as stories: ")
            )
            return "", Stop(
                number,
                head,
                failed + ("the session ran out of time." if timed_out else why),
                "Read the log, then type R and Enter to review this head again.",
                log.as_posix(),
            )
        kept = LOGS / f"{number}-{head[:7]}.{what}.yaml"
        (self.config.root / kept).write_text(
            yaml.safe_dump(entries, sort_keys=False, allow_unicode=True)
        )
        return kept.as_posix(), None

    def _run(
        self,
        number: int,
        head: str,
        env: dict,
        described: dict[str, str] | None = None,
        copy: Path | None = None,
    ) -> tuple[str, bool]:
        """The review session's output, and whether it ran out of time; the session
        runs in the head's copy."""
        argv = self.command(_prompt(self.config, self.repo, number, described, copy))
        return self._session(argv, copy or self.config.root, env, number, head)

    def _session(self, argv, cwd: Path, env: dict, number: int, head: str) -> tuple[str, bool]:
        """A session's output, and whether it ran out of time; a line every few
        minutes says it is still running."""
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        waited = 0
        while True:
            step = min(self.progress, self.timeout - waited)
            try:
                output, _ = process.communicate(timeout=step)
                return output or "", False
            except subprocess.TimeoutExpired:
                waited += step
                if waited >= self.timeout:
                    process.kill()
                    output, _ = process.communicate()
                    return output or "", True
                minutes = waited / 60
                shown = f"{minutes:g} min" if minutes >= 1 else f"{waited} s"
                self.say(f"#{number} head {head[:7]}: still reviewing ({shown})")

    def retry(self) -> None:
        self.paused = False
        for number, head in list(self.stopped):
            if not self.paused:
                self.review(number, head)

    def summary(self) -> str:
        lines = [f"Today: {self.reviews} review session(s), {len(self.stopped)} stopped"]
        lines += [f"  still stopped: #{s.number} ({s.why})" for s in self.stopped.values()]
        return "\n".join(lines)


def _unpack(root: Path, number: int, head: str, into: Path) -> bool:
    """The pull request's head, fetched from the host and unpacked into a folder."""
    import io
    import tarfile

    fetch = subprocess.run(
        ["git", "-C", str(root), "fetch", "-q", "origin", f"pull/{number}/head"],
        capture_output=True,
    )
    if fetch.returncode != 0:
        return False
    archive = subprocess.run(["git", "-C", str(root), "archive", head], capture_output=True)
    if archive.returncode != 0:
        return False
    into.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(into, filter="data")
    return True


def _descriptions(output: str, files: list[str]) -> tuple[list | None, str]:
    """The describe session's list, checked against review.v1 and complete."""
    import yaml

    from tools.validate_contract_tool import validate

    text = output.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:]).rsplit("```", 1)[0]
    try:
        entries = yaml.safe_load(text)
    except yaml.YAMLError as err:
        return None, f"its answer is not YAML ({err.__class__.__name__})."
    problems = validate({"person": "none", "findings": [], "tests": entries}, "review")
    if problems:
        return None, f"its answer breaks review.v1 at '{problems[0].path}': {problems[0].message}"
    missing = sorted(set(files) - {e["file"] for e in entries})
    if missing:
        return None, f"it describes no test of {', '.join(missing)}."
    return entries, ""


def _stories(output: str, config: ProductConfig, files: list[str]) -> tuple[list | None, str]:
    """The storyteller's list, checked against review.v1, a story for every design,
    and every step's source in its design."""
    import yaml

    from tools.classify_pull_request_tool import unsourced
    from tools.validate_contract_tool import validate

    text = output.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:]).rsplit("```", 1)[0]
    try:
        entries = yaml.safe_load(text)
    except yaml.YAMLError as err:
        return None, f"its answer is not YAML ({err.__class__.__name__})."
    problems = validate({"person": "none", "findings": [], "stories": entries}, "review")
    if problems:
        return None, f"its answer breaks review.v1 at '{problems[0].path}': {problems[0].message}"
    designs = {Path(f).name.split(".")[0] for f in files}
    missing = sorted(designs - {e["design"] for e in entries})
    if missing:
        return None, f"it tells no story of {', '.join(missing)}."
    wrong = unsourced(config, entries)
    if wrong:
        return None, f"a step names a source the design does not have: {wrong[0]}."
    return entries, ""


def _copy_head(root: Path, number: int, head: str, into: Path) -> bool:
    """The pull request's head, fetched from the host, as a git worktree of its own:
    the reviewer's folder, never the author's. A copy left from an earlier session
    is replaced."""
    _remove_copy(root, into)
    fetch = subprocess.run(
        ["git", "-C", str(root), "fetch", "-q", "origin", f"pull/{number}/head"],
        capture_output=True,
    )
    if fetch.returncode != 0:
        return False
    add = subprocess.run(
        ["git", "-C", str(root), "worktree", "add", "-q", "--detach", str(into), head],
        capture_output=True,
    )
    return add.returncode == 0


def _remove_copy(root: Path, copy: Path) -> None:
    """The head's copy removed, and git told so."""
    if copy.exists():
        subprocess.run(
            ["git", "-C", str(root), "worktree", "remove", "--force", str(copy)],
            capture_output=True,
        )
        shutil.rmtree(copy, ignore_errors=True)
    subprocess.run(["git", "-C", str(root), "worktree", "prune"], capture_output=True)


def _keep_records(copy: Path, logs: Path) -> None:
    """The records the session wrote in its copy, kept in the product's .qf/reviews/."""
    records = copy / LOGS
    if records.is_dir():
        shutil.copytree(records, logs, dirs_exist_ok=True)


def folder_state(root: Path) -> tuple[str, frozenset[str]] | None:
    """The product folder's commit and changed files, .qf/ left out; None outside git."""
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True
    )
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
    )
    if head.returncode != 0 or status.returncode != 0:
        return None
    lines = {line for line in status.stdout.splitlines() if not line[3:].startswith(".qf/")}
    return head.stdout.strip(), frozenset(lines)


def _changes(before, after) -> str:
    """What changed in the folder between two states, in words; empty when nothing."""
    if before is None or after is None or before == after:
        return ""
    found = []
    if before[0] != after[0]:
        found.append(f"the commit moved from {before[0][:7]} to {after[0][:7]}")
    files = sorted({line[3:] for line in before[1] ^ after[1]})
    if files:
        found.append(", ".join(files[:5]) + (" …" if len(files) > 5 else "") + " changed")
    return "; ".join(found)


def _outcome(state: str) -> str:
    return {
        "APPROVED": "approved; CI decides whether a person reviews it",
        "CHANGES_REQUESTED": "changes requested; the author fixes them",
    }.get(state, f"reviewed ({state.lower()})")


def _stop(
    number: int, head: str, output: str, timed_out: bool, log: str, timeout: int = TIMEOUT
) -> Stop:
    """Why the session ended without a review, and what the person does."""
    if timed_out:
        return Stop(
            number,
            head,
            f"The session ran longer than {timeout // 60} minutes.",
            "Read the log, then type R and Enter to review this head again.",
            log,
        )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    said = {
        k: line.split(":", 1)[1].strip()
        for line in lines
        for k in ("STOPPED", "DO")
        if line.upper().startswith(k + ":")
    }
    if any(code in output for code in ("HTTP 401", "Bad credentials")):
        return Stop(
            number,
            head,
            "The reviewer's token was refused (GitHub answered 401).",
            "Create a new token (QUICKSTART step 3, item 5), save it, and restart the " "watcher.",
            log,
        )
    why = said.get("STOPPED") or (lines[-1] if lines else "The session ended without a word.")
    do = said.get("DO") or "Act on the reason, then type R and Enter to review this head again."
    return Stop(number, head, why, do, log)


def desktop_notification(title: str, text: str) -> None:
    """A notification where the system offers one; nothing otherwise."""
    try:
        if sys.platform == "darwin" and shutil.which("osascript"):
            script = f"display notification {_quoted(text)} with title {_quoted(title)}"
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
        elif sys.platform.startswith("linux") and shutil.which("notify-send"):
            subprocess.run(["notify-send", title, text], capture_output=True, timeout=10)
        elif sys.platform == "win32" and shutil.which("powershell"):
            message = f"[System.Windows.Forms.MessageBox]::Show({_quoted(text)}, {_quoted(title)})"
            subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Add-Type -AssemblyName System.Windows.Forms; {message}",
                ]
            )
    except (OSError, subprocess.SubprocessError):
        pass


def _quoted(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--interval", type=int, default=60, help="seconds between looks")
    parser.add_argument("--command", help="the agent command, {prompt} standing for the prompt")
    parser.add_argument("--once", action="store_true", help="look once, then stop")
    args = parser.parse_args(argv)
    if not os.environ.get(HOST_TOKEN):
        print(
            f"No {HOST_TOKEN}: start the watcher with the reviewer agent's token, in one line "
            "(QUICKSTART step 9).",
            file=sys.stderr,
        )
        return 2
    try:
        config = read_product_config(args.root)
        repo = repository(config.root)
        host = read_host()
        host.default_branch(repo)  # the token reads the repository
    except (ConfigError, HostError) as err:
        print(err, file=sys.stderr)
        return 2
    command = claude_command(config.framework_dir.resolve().as_posix())  # the copy has none
    if args.command:
        template = args.command

        def command(prompt: str) -> list[str]:
            return [part.replace("{prompt}", prompt) for part in shlex.split(template)]

    colour = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    watcher = Watcher(
        config,
        host,
        repo,
        command=command,
        describe=command if args.command else claude_describe_command,
        out=print,
        colour=colour,
        notify=desktop_notification,
    )
    watcher.say(f"Watching {repo} (type R and Enter to retry stopped reviews; Ctrl+C to stop)")
    retry = threading.Event()

    def listen() -> None:
        for line in sys.stdin:
            if line.strip().lower() == "r":
                retry.set()

    threading.Thread(target=listen, daemon=True).start()
    try:
        while True:
            try:
                if retry.is_set():
                    retry.clear()
                    watcher.retry()
                watcher.once()
            except HostError as err:
                watcher.say(f"GitHub could not be read: {err}")
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    print("\n" + watcher.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
