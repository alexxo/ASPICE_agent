"""tools/post_checkpoint_review_tool.py — the person's review in plain words."""

import json

import pytest
from product_builder import (
    AGENT,
    HOST_REPO,
    add_origin,
    build_product,
    git_head,
    note,
    pull_request,
    review,
    write_host,
)

from gates.sup.verify_delivery_reviewed_gate import person_review
from tools import post_checkpoint_review_tool
from tools.post_checkpoint_review_tool import MARK, answers, main, render
from tools.read_host_tool import FileHost
from tools.read_product_config_tool import read_product_config

ASKED = {
    "person": {"condition": 4, "reason": "publishes posts to the live site"},
    "summary": "It publishes the approved posts.",
    "findings": [
        {
            "finding": "the limit is 10, the requirement says 5",
            "outcome": "disputed",
            "author_answer": "5 locks out users on a typo",
            "reviewer_position": "the requirement says 5",
        }
    ],
}


@pytest.fixture
def product(tmp_path):
    root = build_product(tmp_path / "product")
    add_origin(root)
    return root


def _pull(product, tmp_path, record=ASKED, notes=()):
    head = git_head(product)
    data = pull_request(4, head, reviews=[review(AGENT, head, record=record)], notes=notes)
    path = write_host(tmp_path / "host.json", pulls=[data])
    return path, FileHost(path).pull_request(HOST_REPO, 4)


def _render(product, pull, record=ASKED):
    config = read_product_config(product)
    return render(config, HOST_REPO, pull, person_review(config, pull, record), record)


def test_the_review_reads_without_code_what_why_how_then_the_questions(product, tmp_path):
    _, pull = _pull(product, tmp_path)
    body = _render(product, pull)
    assert body.startswith(MARK)
    assert "@lead-bob" in body and "publishes posts to the live site" in body
    what, why, how = (body.index(f"**{part}") for part in ("What this", "Why you", "How to"))
    assert what < why < how < body.index("### 1.")
    assert "It publishes the approved posts." in body
    assert body.rstrip().endswith("</details>")  # the head and the files, folded at the end
    assert [title for title, _ in answers(body)] == [
        "1. Disagreement (disputed)",
        "2. The reviewer agent asks for a person",
    ]


def test_no_person_needed_no_comment(product, tmp_path):
    record = {"person": "none", "findings": []}
    _, pull = _pull(product, tmp_path, record)
    assert _render(product, pull, record) is None


def test_a_person_with_nothing_to_tick_is_still_told_who_and_why(product, tmp_path):
    """FB-43: a change of the product's settings got no comment at all."""
    record = {"person": "none", "findings": [], "summary": "It moves the framework pin."}
    head = git_head(product)
    data = pull_request(25, head, files=["qf.yaml"], reviews=[review(AGENT, head, record=record)])
    pull = FileHost(write_host(tmp_path / "host.json", pulls=[data])).pull_request(HOST_REPO, 25)
    body = _render(product, pull, record)
    assert "@lead-bob" in body and "It changes the product's settings." in body
    assert "nothing to tick" in body and answers(body) == []


@pytest.fixture
def results(tmp_path):
    """The pull request that brings the software tests, its tree's verification
    report written: REQ-0049 passed, REQ-0011 passed elsewhere, REQ-0052 failed."""
    from product_builder import (
        SOFTWARE_TEST,
        build_python_product,
        commit_all,
        write_software_plan,
        write_software_test,
    )

    from tools.write_verification_report_tool import REPORT, report_dir

    root = build_python_product(tmp_path / "product")
    write_software_plan(root)
    write_software_test(root)
    commit_all(root, "test: the software tests")
    rows = [
        {"requirement": "REQ-0049", "level": "software", "kind": "functional",
         "proved_by": "test", "suite": "software", "tests": [SOFTWARE_TEST], "result": "passed"},
        {"requirement": "REQ-0011", "level": "system", "kind": "functional",
         "proved_by": "test", "suite": "e2e", "tests": [], "result": "passed"},
        {"requirement": "REQ-0052", "level": "software", "kind": "security",
         "proved_by": "measurement", "suite": "bench", "threshold": "<= 5 count",
         "measured": [{"value": 6, "met": False}], "result": "failed"},
    ]  # fmt: skip
    config = read_product_config(root)
    folder = report_dir(config)
    folder.mkdir(parents=True)
    (folder / REPORT).write_text(json.dumps({"software": rows}))
    told = {"file": SOFTWARE_TEST, "test": "the form takes the sign-in", "prepares": "an email",
            "does": "sends the form", "checks": "it is taken", "not": "a wrong email"}  # fmt: skip
    record = {"person": "none", "findings": [], "summary": "It brings the results.",
              "tests": [told]}  # fmt: skip
    head = git_head(root)
    reviews = [review(AGENT, head, record=record)]
    data = pull_request(30, head, files=[SOFTWARE_TEST], reviews=reviews)
    pull = FileHost(write_host(tmp_path / "host.json", pulls=[data])).pull_request(HOST_REPO, 30)
    return config, pull, record


def test_the_results_ask_what_matters_and_count_the_rest(results):
    """FB-45: checkpoint 4 is the person's approval of the results."""
    config, pull, record = results
    body = render(config, HOST_REPO, pull, person_review(config, pull, record), record)
    assert [title for title, _ in answers(body)] == [
        "1. “The form takes an email and a password.”",
        "2. “The web app rejects a malformed sign-in form.”",
    ]
    assert "3 requirements · 2 passed · 1 failed · 0 not run. You tick 2" in body
    first, second = body.split("### ")[1:3]
    assert "*Given* an email" in first and "**Result:** passed" in first
    assert "**Measured:** 6 (threshold <= 5 count)" in second and "**failed**" in second
    assert "- [ ] 1. achieved\n- [ ] 2. not achieved" in first
    assert "**Question:** Is this requirement achieved?" in first
    assert "**Proposed:** 1. achieved — the test passed." in first


def test_without_the_verification_report_the_results_wait(results):
    import shutil

    from tools.write_verification_report_tool import report_dir

    config, pull, record = results
    shutil.rmtree(report_dir(config))
    assert render(config, HOST_REPO, pull, person_review(config, pull, record), record) is None


GAP = {
    "design": "auth-service",
    "story": "A wrong password",
    "step": "The design does not say how long.",
    "now": "The session stays open 30 minutes.",
    "source": ["src/auth.py:12"],
    "means": "A user away for half an hour signs in again.",
}


@pytest.mark.parametrize(
    ("gap", "told"),
    [
        (GAP, "**Now:** The session stays open 30 minutes. (`src/auth.py:12`)"),
        (
            {**GAP, "source": [], "now": "30 minutes"},
            "**Now:** nothing decides it yet; the build will take this reading: 30 minutes",
        ),
    ],
)
def test_a_gap_of_a_design_says_what_keeping_it_keeps(product, tmp_path, gap, told):
    """FB-54: "keep" keeps a named behaviour, and the person sees what it means."""
    step = {"text": "The design does not say how long.", "source": ["unit:x"], "gap": True}
    story = {"design": "auth-service", "story": "A wrong password", "steps": [step]}
    record = {"person": "none", "findings": [], "summary": "It designs the sign-in."}
    record["stories"] = [story]
    record["gaps"] = [gap]
    head = git_head(product)
    files = ["docs/design/auth-service.md"]
    data = pull_request(26, head, files=files, reviews=[review(AGENT, head, record=record)])
    pull = FileHost(write_host(tmp_path / "host.json", pulls=[data])).pull_request(HOST_REPO, 26)
    body = _render(product, pull, record)
    assert [title for title, _ in answers(body)] == [
        "1. An open question in the design of auth-service"
    ]
    assert f"⚠ The design does not say how long.\n\n{told}\n" in body
    assert "**For the user:** A user away for half an hour signs in again." in body
    assert "- [ ] 1. keep it as it is now\n- [ ] 2. change it" in body
    assert "**Question:** Do you keep what the product does here now?" in body


@pytest.mark.parametrize(
    ("boxes", "answer"),
    [("[x] yes\n- [ ] no", "yes"), ("[ ] yes\n- [x] no", "no"), ("[x] yes\n- [x] no", None)],
)
def test_the_first_box_alone_is_yes(boxes, answer):
    assert answers(f"### 1. An item\n\ntext\n\n- {boxes}\n") == [("1. An item", answer)]


@pytest.fixture
def posted(monkeypatch):
    monkeypatch.setenv("QF_HOST_TOKEN", "run-token")
    sent = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        sent.append(request)
        return Response()

    monkeypatch.setattr(post_checkpoint_review_tool.urllib.request, "urlopen", urlopen)
    return sent


def test_ci_posts_the_review_once_per_head_and_items(product, tmp_path, monkeypatch, posted):
    path, pull = _pull(product, tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(path))
    assert main(["--root", str(product), "--pull-request", "4"]) == 0
    (request,) = posted
    assert request.full_url.endswith(f"/repos/{HOST_REPO}/issues/4/comments")
    assert request.get_method() == "POST"
    body = json.loads(request.data)["body"]

    path, _ = _pull(product, tmp_path, notes=[note(body, "2026-10-24T09:00:00Z", id=77)])
    monkeypatch.setenv("QF_HOST_FILE", str(path))
    assert main(["--root", str(product), "--pull-request", "4"]) == 0
    assert len(posted) == 1  # already posted: an approval stays valid


def test_a_new_head_rewrites_the_one_comment(product, tmp_path, monkeypatch, posted):
    _, pull = _pull(product, tmp_path)
    older = _render(product, pull).replace(pull.head, "0" * 40)
    path, _ = _pull(product, tmp_path, notes=[note(older, "2026-10-24T09:00:00Z", id=77)])
    monkeypatch.setenv("QF_HOST_FILE", str(path))
    assert main(["--root", str(product), "--pull-request", "4"]) == 0
    (request,) = posted
    assert request.full_url.endswith(f"/repos/{HOST_REPO}/issues/comments/77")
    assert request.get_method() == "PATCH"


def test_without_the_reviewer_agents_record_nothing_is_posted(
    product, tmp_path, monkeypatch, posted
):
    path, _ = _pull(product, tmp_path, record=None)
    monkeypatch.setenv("QF_HOST_FILE", str(path))
    assert main(["--root", str(product), "--pull-request", "4"]) == 0
    assert posted == []
