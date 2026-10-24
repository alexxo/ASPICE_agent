"""tools/watch_reviews_tool.py — the reviewer starts on its own; a stop is impossible to miss."""

import sys
from dataclasses import replace

import pytest
from product_builder import AGENT, HOST_REPO, build_product, pull_request, write_host

from tools.read_host_tool import FileHost, Review
from tools.read_product_config_tool import read_product_config
from tools.watch_reviews_tool import Stop, Watcher, banner, claude_command, due, tools

WAITING = "Wait: the reviewer agent's approval"


def _host(tmp_path, signs, reviews=()):
    pulls = [pull_request(n, f"{n}" * 40, reviews=reviews) for n in (7, 8)]
    return FileHost(write_host(tmp_path / "host.json", pulls=pulls, signs=signs))


def test_only_heads_waiting_for_the_reviewer_are_due(tmp_path):
    host = _host(tmp_path, {"7" * 40: WAITING, "8" * 40: "Wait: gates running"})
    assert due(host, HOST_REPO, {AGENT}, set()) == [(7, "7" * 40)]


def test_every_head_is_reviewed_once(tmp_path):
    host = _host(tmp_path, {"7" * 40: WAITING})
    assert due(host, HOST_REPO, {AGENT}, {(7, "7" * 40)}) == []
    reviewed = [{"author": AGENT, "state": "APPROVED", "commit": "7" * 40, "body": ""}]
    assert due(_host(tmp_path, {"7" * 40: WAITING}, reviewed), HOST_REPO, {AGENT}, set()) == []


def test_the_banner_says_why_what_to_do_and_where_the_log_is():
    why, do = "The reviewer's token was refused.", "Create a new token."
    stop = Stop(26, "a41c9e0" * 6, why, do, "x.log")
    text = banner(stop)
    lines = text.splitlines()
    assert lines[0] == lines[-1] == "#" * 72
    assert "REVIEW STOPPED: pull request #26, head a41c9e0" in lines[1]
    assert "#  Why:   The reviewer's token was refused." in lines
    assert "#  Do:    Create a new token." in lines
    assert "#  Log:   x.log" in lines
    assert banner(stop, colour=True).startswith("\033[1;31m")


def test_the_reviewer_runs_with_its_own_tools_only():
    allowed = tools(".framework")
    assert "Bash(python .framework/tools/post_review_tool.py:*)" in allowed
    assert not any(t.startswith(("Edit", "Bash(git push", "Bash(git commit")) for t in allowed)
    assert not any(t in ("Bash(python:*)", "Bash", "Write") for t in allowed)
    argv = claude_command(".framework")("review #7")
    assert argv[:3] == ["claude", "-p", "review #7"]


class _Host:
    """A host the fake reviewer posts to."""

    def __init__(self, tmp_path):
        self.base = _host(tmp_path, {"7" * 40: WAITING})
        self.posted = []

    def open_pull_requests(self, repo):
        return [7]

    def merge_sign(self, repo, sha):
        return WAITING

    def pull_request(self, repo, number):
        pull = self.base.pull_request(repo, number)
        return replace(pull, reviews=tuple(self.posted))


@pytest.fixture
def watcher(tmp_path):
    root = build_product(tmp_path / "product", git=False)
    host = _Host(tmp_path)
    shown = []
    notes = []
    w = Watcher(
        read_product_config(root),
        host,
        HOST_REPO,
        out=shown.append,
        notify=lambda title, text: notes.append(title),
    )
    return w, host, shown, notes


def _speaks(text):
    return lambda prompt: [sys.executable, "-c", f"print({text!r})"]


def test_a_posted_review_is_one_line(watcher):
    w, host, shown, notes = watcher

    def review(prompt):
        host.posted.append(Review(AGENT, "APPROVED", "7" * 40))
        return [sys.executable, "-c", "print('approved')"]

    w.command = review
    w.once()
    assert shown[-1].endswith("#7 head 7777777: approved; CI decides whether a person reviews it")
    assert notes == [] and w.stopped == {}


def test_a_session_ending_without_a_review_is_a_banner(watcher):
    w, host, shown, notes = watcher
    w.command = _speaks("STOPPED: REQ-0014 reads two ways.\nDO: Answer on the pull request.")
    w.once()
    assert "REVIEW STOPPED: pull request #7" in shown[-1]
    assert "REQ-0014 reads two ways." in shown[-1]
    assert notes == ["Review stopped: #7"]
    log = w.config.root / ".qf/reviews/7-7777777.log"
    assert "STOPPED:" in log.read_text()


def test_a_refused_token_says_to_make_a_new_one(watcher):
    w, host, shown, _ = watcher
    w.command = _speaks("GitHub refused /repos/acme/login: HTTP 401")
    w.once()
    assert "token was refused" in shown[-1] and "QUICKSTART step 3, item 5" in shown[-1]


def test_a_stopped_head_waits_for_r_and_the_summary_lists_it(watcher):
    w, host, shown, _ = watcher
    w.command = _speaks("STOPPED: no answer.")
    w.once()
    w.once()  # not retried on its own
    assert w.reviews == 1
    assert "still stopped: #7 (no answer.)" in w.summary()

    def review(prompt):
        host.posted.append(Review(AGENT, "CHANGES_REQUESTED", "7" * 40))
        return [sys.executable, "-c", "print('done')"]

    w.command = review
    w.retry()
    assert w.stopped == {} and "changes requested" in shown[-1]
