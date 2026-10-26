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
    edits = [t for t in allowed if t.startswith(("Edit", "Write"))]
    assert edits == ["Edit(.qf/reviews/**)"]  # its record's folder only
    assert not any(t.startswith(("Bash(git push", "Bash(git commit")) for t in allowed)
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
        copy=_folder,
    )
    return w, host, shown, notes


def _folder(root, number, head, into):
    """A copy of the head without git, for a host whose heads are made up."""
    into.mkdir(parents=True, exist_ok=True)
    return True


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


def test_a_long_review_says_it_is_alive_and_a_stuck_one_stops(watcher):
    w, host, shown, notes = watcher
    w.progress, w.timeout = 1, 3
    w.command = lambda prompt: [sys.executable, "-c", "import time; time.sleep(30)"]
    w.once()
    progress = [line for line in shown if "still reviewing" in line]
    assert [line.split(": ", 1)[1] for line in progress] == [
        "still reviewing (1 s)",
        "still reviewing (2 s)",
    ]
    assert "The session ran longer than 0 minutes." in shown[-1]
    assert notes == ["Review stopped: #7"]


def test_the_reviewer_writes_its_record_by_an_edit_rule():
    """FB-47: Claude Code matches file permissions by Edit rules only."""
    allowed = tools(".framework")
    assert "Edit(.qf/reviews/**)" in allowed and "Write(.qf/reviews/**)" not in allowed


def test_a_usage_limit_is_tried_again_on_its_own(watcher):
    """FB-47: the limit resets; the head is reviewed then, without the person."""
    w, host, shown, notes = watcher
    now = [0.0]
    w.clock = lambda: now[0]
    w.command = _speaks("You've hit your session limit · resets 1:50pm (Europe/Berlin)")
    w.once()
    said = " ".join(line.strip("# ") for line in shown[-1].splitlines())
    assert "usage limit was reached" in said and "tries this head again" in said
    now[0] = 9 * 60
    w.once()
    assert w.reviews == 1  # not before 10 minutes
    now[0] = 10 * 60
    w.once()
    assert w.reviews == 2
    assert shown[-1].endswith("usage limit still reached; trying again in 10 min")
    assert notes == ["Review stopped: #7"]  # one banner, then one line per try

    def review(prompt):
        host.posted.append(Review(AGENT, "APPROVED", "7" * 40))
        return [sys.executable, "-c", "print('reviewed')"]

    w.command = review
    now[0] = 20 * 60
    w.once()
    assert "approved" in shown[-1] and w.stopped == {} and w.limited == {}


class _Signs:
    """A host whose pull request #9 moves through the crossing signs."""

    def __init__(self):
        self.sign = None
        self.head = "9" * 40

    def open_pull_requests(self, repo):
        return [9]

    def merge_sign(self, repo, sha):
        return self.sign

    def pull_request(self, repo, number):
        from tools.read_host_tool import PullRequest

        return PullRequest(9, "dev-alice", self.head)


def test_every_change_of_state_is_one_line_naming_who_acts(watcher):
    w, _, shown, _ = watcher
    host = w.host = _Signs()
    now = [0.0]
    w.clock = lambda: now[0]
    states = []
    for sign in [
        None,
        "Wait: gates running",
        "Wait: gates running",
        "Wait: gates red: verify_test_first_gate",
        "Wait: a review by lead-bob (the feature's results are ready for your approval): approve",
        "Ready to merge",
    ]:
        host.sign = sign
        w.once()
    states = [line.split(": ", 1)[1] for line in shown]
    assert states == [
        "waits for CI (gates running)",
        "gates red (verify_test_first_gate): the author fixes them, no review yet",
        f"waits for a review by lead-bob: https://github.com/{HOST_REPO}/pull/9/files",
        "ready to merge; the agent merges",
    ]


def test_the_person_is_sent_to_cis_comment_when_there_is_one(watcher):
    """FB-43: the line pointed to "the link in the pull request", which did not exist."""
    from tools.post_checkpoint_review_tool import MARK
    from tools.read_host_tool import Note, PullRequest

    w, *_ = watcher
    ours = Note(4242, "github-actions[bot]", f"{MARK}\n…", "2026-10-25T09:00:00Z", bot=True)
    pull = PullRequest(9, "dev-alice", "9" * 40, notes=(ours,))
    assert w.state(9, pull.head, "Wait: a review by lead-bob: approve again", True, pull) == (
        f"waits for a review by lead-bob: https://github.com/{HOST_REPO}/pull/9#issuecomment-4242"
    )


def test_a_head_without_a_sign_for_10_minutes_is_a_warning(watcher):
    w, _, shown, _ = watcher
    w.host = _Signs()
    now = [0.0]
    w.clock = lambda: now[0]
    w.once()
    assert shown == []
    now[0] = 600
    w.once()
    w.once()
    assert [line.split(": ", 1)[1] for line in shown] == [
        "no crossing sign after 10 min: check that CI runs"
    ]


def test_a_reviewer_that_changes_the_work_pauses_every_review(changed):
    w, shown, head = changed
    notes = []
    w.notify = lambda title, text: notes.append(title)
    edit = "open('NOTES.md', 'w').write('changed by the reviewer')"
    w.command = lambda prompt: [sys.executable, "-c", edit]
    w.once()
    assert "REVIEWER CHANGED THE WORK: pull request #7" in shown[-1]
    said = " ".join(line.strip("# ") for line in shown[-1].splitlines())
    assert "NOTES.md changed" in said and "Verify your LLM settings" in said
    copy = w.config.root / f".qf/reviews/7-{head[:7]}"
    assert "copy is kept" in said and (copy / "NOTES.md").read_text() == "changed by the reviewer"
    assert notes == ["Reviewer changed the work: #7"] and w.paused
    w.once()
    assert w.reviews == 1  # paused: no review until R

    def review(prompt):
        w.host.posted.append(Review(AGENT, "APPROVED", head))
        return [sys.executable, "-c", "print('reviewed')"]

    w.command = review
    w.retry()  # on a fresh copy
    assert not w.paused and "approved" in shown[-1]
    assert not copy.exists()  # removed after the review


def test_the_authors_work_during_a_review_is_not_the_reviewers(changed):
    """FB-46: the author and the framework go on working in the product folder."""
    w, shown, head = changed
    author = f"open({str(w.config.root / 'NOTES.md')!r}, 'w').write('the author goes on')"

    def review(prompt):
        assert "make no copy of your own" in prompt
        w.host.posted.append(Review(AGENT, "APPROVED", head))
        return [sys.executable, "-c", author]

    w.command = review
    w.once()
    assert not w.paused and "approved" in shown[-1]
    assert (w.config.root / "NOTES.md").read_text() == "the author goes on"


def test_the_reviewers_own_folder_is_not_the_work(changed):
    w, shown, head = changed
    record = "import os; os.makedirs('.qf/reviews', exist_ok=True); "
    record += "open('.qf/reviews/review.yaml', 'w').write('person: none')"
    w.command = lambda prompt: [sys.executable, "-c", record]
    w.once()
    assert not w.paused and "REVIEW STOPPED" in shown[-1]
    assert (w.config.root / ".qf/reviews/review.yaml").read_text() == "person: none"


def test_a_head_that_cannot_be_fetched_stops_the_review(tmp_path):
    root = build_product(tmp_path / "product")  # no origin
    shown = []
    w = Watcher(read_product_config(root), _Host(tmp_path), HOST_REPO, out=shown.append)
    w.command = lambda prompt: pytest.fail("the review must not start")
    w.once()
    said = " ".join(line.strip("# ") for line in shown[-1].splitlines())
    assert "REVIEW STOPPED" in said and "could not be fetched" in said


DESCRIBER = """
import os, sys
seen = sorted(os.path.join(d, f) for d, _, fs in os.walk('.') for f in fs)
assert seen == ['./st/software/test_sign_in_form.py'], seen
print('```yaml')
print('- file: st/software/test_sign_in_form.py')
print('  test: test_the_form_takes_the_sign_in')
print('  prepares: the value 1')
print('  does: runs the unit')
print('  checks: the answer is 2')
print('  not: nothing obvious')
print('```')
"""


EXPECTER = """
import os, yaml
seen = sorted(os.path.join(d, f) for d, _, fs in os.walk('.') for f in fs)
assert seen == ['./criteria.yaml', './docs/glossary.md'], seen
assert 'QF_HOST_TOKEN' not in os.environ and 'GH_TOKEN' not in os.environ
for req in yaml.safe_load(open('criteria.yaml')):
    print(f"- requirement: {req['requirement']}")
    print("  criterion: 1")
    print("  case: the sign-in is taken")
"""


def _sessions(expecter=EXPECTER):
    """The describe sessions: the tests described, the expected cases listed."""
    return lambda prompt: [
        sys.executable,
        "-c",
        DESCRIBER if prompt.startswith("Describe the tests") else expecter,
    ]


def _on_origin(tmp_path, change, files):
    """A Python product whose pull request #7, the change of these files, is on
    its origin."""
    import subprocess

    from product_builder import build_python_product, commit_all, git_head

    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    root = build_python_product(tmp_path / "product")
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", str(origin)], check=True)
    change(root)
    commit_all(root, "the change of pull request #7")
    head = git_head(root)
    subprocess.run(["git", "-C", str(root), "push", "-q", "origin", "HEAD:refs/pull/7/head"])
    subprocess.run(["git", "-C", str(root), "checkout", "-q", "main"], check=True)

    class Host:
        posted = []

        def open_pull_requests(self, repo):
            return [7]

        def merge_sign(self, repo, sha):
            return WAITING

        def pull_request(self, repo, number):
            from tools.read_host_tool import PullRequest

            return PullRequest(7, "dev-alice", head, tuple(files), tuple(self.posted))

    shown = []
    w = Watcher(read_product_config(root), Host(), HOST_REPO, out=shown.append)
    return w, shown, head


@pytest.fixture
def pulled(tmp_path):
    """Pull request #7 adds the software-level tests: it brings the results."""
    from product_builder import SOFTWARE_TEST, write_software_plan, write_software_test

    def change(root):
        write_software_plan(root)
        write_software_test(root)

    return _on_origin(tmp_path, change, [SOFTWARE_TEST])


@pytest.fixture
def changed(tmp_path):
    """Pull request #7 adds a note."""

    def change(root):
        (root / "NOTES.md").write_text("a note")

    return _on_origin(tmp_path, change, ["NOTES.md"])


@pytest.fixture
def redesigned(tmp_path):
    """Pull request #7 changes the detailed design of auth-service."""

    def change(root):
        design = root / "docs/design/auth-service.md"
        design.write_text("- **D1 — failures are counted per account.**\n\n" + design.read_text())

    return _on_origin(tmp_path, change, ["docs/design/auth-service.md"])


STORYTELLER = """
import os
seen = sorted(os.path.join(d, f) for d, _, fs in os.walk('.') for f in fs)
assert seen == ['./docs/design/auth-service.md', './docs/design/auth-service.sequence.json'], seen
assert 'QF_HOST_TOKEN' not in os.environ and 'GH_TOKEN' not in os.environ
print('- design: auth-service')
print('  story: A wrong password')
print('  steps:')
print('    - text: The credentials are checked; failures are counted per account.')
print('      source: [unit:check-credentials, decision:D1]')
print('    - text: The design does not say what happens after five failures.')
print('      source: [unit:count-failures]')
print('      gap: true')
"""


def test_the_watcher_tells_the_design_as_stories_in_a_folder_of_designs_only(
    redesigned, monkeypatch
):
    w, shown, head = redesigned
    monkeypatch.setenv("QF_HOST_TOKEN", "reviewer-token")
    prompts = []
    w.describe = lambda prompt: [sys.executable, "-c", STORYTELLER]

    def review(prompt):
        prompts.append(prompt)
        w.host.posted.append(Review(AGENT, "APPROVED", head))
        return [sys.executable, "-c", "print('reviewed')"]

    w.command = review
    w.once()
    told = f".qf/reviews/7-{head[:7]}.stories.yaml"
    assert told in prompts[0] and "never write or change a story yourself" in prompts[0]
    assert "gap: true" in (w.config.root / told).read_text()
    assert "approved" in shown[-1]


def test_a_story_with_an_invented_source_stops_the_review(redesigned):
    w, shown, head = redesigned
    invented = STORYTELLER.replace("decision:D1", "unit:send-email")
    w.describe = lambda prompt: [sys.executable, "-c", invented]
    w.command = lambda prompt: pytest.fail("the review must not start")
    w.once()
    said = " ".join(line.strip("# ") for line in shown[-1].splitlines())
    assert "The designs could not be told as stories" in said and "unit:send-email" in said


def test_the_watcher_describes_the_tests_in_a_folder_of_tests_only(pulled):
    w, shown, head = pulled
    prompts = []
    w.describe = _sessions()

    def review(prompt):
        prompts.append(prompt)
        w.host.posted.append(Review(AGENT, "APPROVED", head))
        return [sys.executable, "-c", "print('reviewed')"]

    w.command = review
    w.once()
    described = f".qf/reviews/7-{head[:7]}.tests.yaml"
    assert described in prompts[0] and "never describe a test yourself" in prompts[0]
    assert "test: test_the_form_takes_the_sign_in" in (w.config.root / described).read_text()
    assert not (w.config.root / ".qf/reviews/7-head").exists()  # cleaned up
    assert "approved" in shown[-1]


def test_the_watcher_lists_the_expected_cases_from_the_criteria_alone(pulled):
    w, shown, head = pulled
    prompts = []
    w.describe = _sessions()

    def review(prompt):
        prompts.append(prompt)
        w.host.posted.append(Review(AGENT, "APPROVED", head))
        return [sys.executable, "-c", "print('reviewed')"]

    w.command = review
    w.once()
    listed = f".qf/reviews/7-{head[:7]}.expected.yaml"
    assert listed in prompts[0] and "never add, drop or change a case yourself" in prompts[0]
    cases = (w.config.root / listed).read_text()
    assert [line for line in cases.splitlines() if "requirement" in line] == [
        "- requirement: REQ-0049",
        "- requirement: REQ-0050",
        "- requirement: REQ-0053",
    ]
    assert "approved" in shown[-1]


@pytest.mark.parametrize(
    ("answer", "why"),
    [
        ("print('- requirement: REQ-0049')", "breaks review.v1"),
        (
            "print('- {requirement: REQ-0049, criterion: 1, case: c}')",
            "it lists no case of REQ-0050, REQ-0053",
        ),
        (
            "print('- {requirement: REQ-0049, criterion: 9, case: c}')",
            "a criterion that does not exist: REQ-0049 criterion 9",
        ),
    ],
)
def test_expected_cases_that_fail_stop_the_review_before_it_starts(pulled, answer, why):
    w, shown, head = pulled
    w.describe = _sessions(answer)
    w.command = lambda prompt: pytest.fail("the review must not start")
    w.once()
    said = " ".join(line.strip("# ") for line in shown[-1].splitlines())
    assert "The expected cases could not be listed" in said and why in said


def test_descriptions_that_fail_stop_the_review_before_it_starts(pulled):
    w, shown, head = pulled
    w.describe = lambda prompt: [sys.executable, "-c", "print('I looked at the requirements.')"]
    w.command = lambda prompt: pytest.fail("the review must not start")
    w.once()
    said = " ".join(line.strip("# ") for line in shown[-1].splitlines())
    assert "REVIEW STOPPED" in said and "The tests could not be described" in said


def test_the_watcher_starts_as_quickstart_says(tmp_path, monkeypatch, capsys):
    """main() as far as its first look, on a recorded host (FB-42: a field added to
    Watcher once shifted main()'s arguments, and the watcher crashed at start)."""
    from product_builder import add_origin

    from tools import watch_reviews_tool

    root = build_product(tmp_path / "product")
    add_origin(root)
    monkeypatch.setenv("QF_HOST_TOKEN", "reviewer-token")
    monkeypatch.setenv("QF_HOST_FILE", str(write_host(tmp_path / "host.json")))
    built = []
    real = watch_reviews_tool.Watcher

    def spy(*args, **kwargs):
        built.append(real(*args, **kwargs))
        return built[-1]

    monkeypatch.setattr(watch_reviews_tool, "Watcher", spy)
    assert watch_reviews_tool.main(["--root", str(root), "--once"]) == 0
    out = capsys.readouterr().out
    assert f"Watching {HOST_REPO}" in out and "Today: 0 review session(s)" in out
    (w,) = built
    assert w.out is print and callable(w.command) and callable(w.describe)
    assert callable(w.notify) and isinstance(w.colour, bool)
