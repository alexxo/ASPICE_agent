"""tools/read_host_tool.py — pull requests, reviews, checks and tags from the host."""

import json
import subprocess

import pytest
from product_builder import (
    AGENT,
    AUTHOR,
    HOST_REPO,
    PERSON,
    add_origin,
    commit_all,
    git_head,
    pull_request,
    review,
    write_host,
)

from tools.read_host_tool import (
    FileHost,
    GitHubHost,
    HostError,
    PullRequest,
    Review,
    delivery,
    read_host,
    remote_slug,
    repository,
)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "product"
    root.mkdir()
    (root / "README.md").write_text("product\n")
    commit_all(root, "start")
    subprocess.run(["git", "-C", str(root), "branch", "-M", "main"], check=True)
    add_origin(root)
    return root


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/acme/login.git",
        "https://github.com/acme/login",
        "git@github.com:acme/login.git",
        "ssh://git@github.com/acme/login.git",
    ],
)
def test_the_repository_is_read_from_any_github_remote(url):
    assert remote_slug(url) == "acme/login"


def test_a_remote_elsewhere_has_no_slug():
    assert remote_slug("https://gitlab.com/acme/login.git") is None
    assert remote_slug("../framework.git") is None


def test_ci_names_the_repository_before_the_remote(repo, monkeypatch):
    assert repository(repo) == HOST_REPO
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/other")
    assert repository(repo) == "acme/other"


def test_without_token_or_file_the_host_cannot_be_read():
    with pytest.raises(HostError, match="QF_HOST_TOKEN"):
        read_host()


def test_a_host_file_replaces_the_api(tmp_path, monkeypatch):
    monkeypatch.setenv("QF_HOST_FILE", str(write_host(tmp_path / "host.json")))
    assert isinstance(read_host(), FileHost)
    monkeypatch.setenv("QF_HOST_TOKEN", "t")
    assert isinstance(read_host(), FileHost)
    monkeypatch.delenv("QF_HOST_FILE")
    assert isinstance(read_host(), GitHubHost)


def test_only_each_reviewers_latest_decision_on_the_head_counts():
    head = "b" * 40
    pull = PullRequest(
        1,
        AUTHOR,
        head,
        reviews=(
            Review("one", "APPROVED", head),
            Review("one", "COMMENTED", head),  # a comment keeps the approval
            Review("two", "APPROVED", head),
            Review("two", "CHANGES_REQUESTED", head),  # a later decision replaces it
            Review("three", "APPROVED", "a" * 40),  # an older head
            Review("four", "APPROVED", head),
            Review("four", "DISMISSED", head),
        ),
    )
    assert [r.author for r in pull.approvals()] == ["one"]


def test_the_delivery_of_a_ci_pull_request_event(repo, tmp_path, monkeypatch):
    head = git_head(repo)
    host = FileHost(write_host(tmp_path / "h.json", pulls=[pull_request(7, head)]))
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 7}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    found = delivery(repo, host)
    assert (found.pull_request.number, found.on_main) == (7, False)


def test_the_delivery_of_a_branch_is_its_open_pull_request(repo, tmp_path):
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "feature/x"], check=True)
    head = git_head(repo)
    pulls = [
        pull_request(3, head, branch="feature/x", merged=True),
        pull_request(4, head, branch="feature/x", reviews=[review(AGENT, head)]),
    ]
    found = delivery(repo, FileHost(write_host(tmp_path / "h.json", pulls=pulls)))
    assert found.pull_request.number == 4
    assert found.pull_request.reviews[0].author == AGENT


def test_a_branch_without_pull_request_has_no_delivery(repo, tmp_path):
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "feature/x"], check=True)
    found = delivery(repo, FileHost(write_host(tmp_path / "h.json")))
    assert (found.pull_request, found.on_main) == (None, False)


def test_on_main_the_delivery_is_the_merged_pull_request_of_the_head(repo, tmp_path):
    head = git_head(repo)
    pulls = [pull_request(9, "c" * 40, merged=True, commits=[head])]
    found = delivery(repo, FileHost(write_host(tmp_path / "h.json", pulls=pulls)))
    assert (found.pull_request.number, found.on_main) == (9, True)


def test_github_passed_checks_are_read_from_the_api(monkeypatch):
    sha = "a" * 40
    answers = {
        f"/repos/acme/login/commits/{sha}/check-runs?per_page=100": {
            "check_runs": [
                {"name": "gates", "conclusion": "failure"},
                {"name": "gates", "conclusion": "success"},  # a re-run that passed
                {"name": "lint", "conclusion": None, "status": "in_progress"},
            ]
        }
    }
    host = GitHubHost("token")
    monkeypatch.setattr(host, "_get", lambda path: answers.get(path))
    assert host.passed_checks(HOST_REPO, sha) == {"gates"}
    assert host.passed_checks(HOST_REPO, "b" * 40) == frozenset()


def test_recorded_checks_pass_every_head_unless_given(tmp_path):
    pulls = [pull_request(1, "c" * 40)]
    host = FileHost(write_host(tmp_path / "host.json", pulls=pulls))
    assert host.passed_checks(HOST_REPO, "c" * 40) == {"gates"}
    red = FileHost(write_host(tmp_path / "red.json", pulls=pulls, checks={}))
    assert red.passed_checks(HOST_REPO, "c" * 40) == frozenset()


def test_github_release_tags_name_their_commits(monkeypatch):
    pages = {
        "/repos/acme/quality-framework/tags?per_page=100&page=1": [
            {"name": "v6.0.0", "commit": {"sha": "c6"}},
            {"name": "v5.0.0", "commit": {"sha": "c5"}},
        ]
    }
    host = GitHubHost("token")
    monkeypatch.setattr(host, "_get", lambda path: pages.get(path))
    assert host.release_tags("acme/quality-framework") == {"v6.0.0": "c6", "v5.0.0": "c5"}


def test_github_reviews_keep_the_head_and_whether_a_bot_wrote_them(monkeypatch):
    pages = {
        "/repos/acme/login/pulls/5": {
            "user": {"login": AUTHOR},
            "head": {"sha": "h1"},
            "merged": False,
        },
        "/repos/acme/login/pulls/5/files?per_page=100&page=1": [{"filename": "a.py"}],
        "/repos/acme/login/pulls/5/reviews?per_page=100&page=1": [
            {"user": {"login": AGENT, "type": "User"}, "state": "APPROVED", "commit_id": "h1"},
            {"user": {"login": "ci[bot]", "type": "Bot"}, "state": "APPROVED", "commit_id": "h1"},
        ],
    }
    host = GitHubHost("token")
    monkeypatch.setattr(host, "_get", lambda path: pages.get(path))
    pull = host.pull_request(HOST_REPO, 5)
    assert pull.files == ("a.py",)
    assert [(r.author, r.bot, r.commit) for r in pull.reviews] == [
        (AGENT, False, "h1"),
        ("ci[bot]", True, "h1"),
    ]


def test_github_issues_leave_out_pull_requests_and_keep_their_comments(monkeypatch):
    pages = {
        "/repos/acme/login/issues?state=all&labels=non-conformance&per_page=100&page=1": [
            {
                "number": 7,
                "user": {"login": AUTHOR},
                "state": "open",
                "created_at": "2026-10-01T09:00:00Z",
                "closed_at": None,
                "labels": [{"name": "non-conformance"}, {"name": "escalated"}],
                "assignees": [{"login": PERSON}],
                "body": "```yaml nonconformance\nfound_in: 3\n```\n",
            },
            {"number": 8, "pull_request": {}, "state": "open"},
        ],
        "/repos/acme/login/issues/7/comments?per_page=100&page=1": [
            {"user": {"login": PERSON}, "body": "Looking.", "created_at": "2026-10-02T09:00:00Z"}
        ],
    }
    host = GitHubHost("token")
    monkeypatch.setattr(host, "_get", lambda path: pages.get(path))
    (issue,) = host.issues(HOST_REPO, "non-conformance")
    assert (issue.number, issue.labels, issue.assignees) == (
        7,
        ("non-conformance", "escalated"),
        (PERSON,),
    )
    assert issue.comments[0].author == PERSON
    assert issue.record("nonconformance") == ({"found_in": 3}, None)


def test_an_issue_block_counts_only_alone_and_following_its_contract():
    from tools.read_host_tool import Issue

    def issue(body):
        return Issue(1, AUTHOR, "open", "2026-10-01T09:00:00Z", body=body)

    block = "```yaml retro_action\nowner: lead-bob\ndue: 2026-11-15\n```\n"
    assert issue(block).record("retro_action")[0] == {"owner": "lead-bob", "due": "2026-11-15"}
    assert "holds 0" in issue("No block.").record("retro_action")[1]
    assert "holds 2" in issue(block + block).record("retro_action")[1]
    assert (
        "breaks retro_action.v1"
        in issue(block.replace("2026-11-15", "soon")).record("retro_action")[1]
    )


def test_a_command_is_the_first_line_of_a_comment():
    from tools.read_host_tool import Comment, Issue

    said = [
        Comment(PERSON, "/confirm-fixed\nThanks.", "2026-10-02T09:00:00Z"),
        Comment(PERSON, "I will /confirm-fixed later.", "2026-10-03T09:00:00Z"),
    ]
    issue = Issue(1, AUTHOR, "open", "2026-10-01T09:00:00Z", comments=tuple(said))
    assert issue.commands("/confirm-fixed") == said[:1]
