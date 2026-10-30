"""tools/classify_pull_request_tool.py — a person for the results and what is wanted."""

import re

import pytest
from product_builder import (
    SOFTWARE_TEST,
    build_python_product,
    commit_all,
    edit_plan,
    unit_path,
    write_code,
    write_software_plan,
    write_software_test,
    write_unit_test,
)

from tools.classify_pull_request_tool import classify, headline, unsourced
from tools.read_product_config_tool import read_product_config

DISPUTE = {
    "finding": "the limit is 10, the requirement says 5",
    "outcome": "disputed",
    "author_answer": "5 locks out users on a typo",
    "reviewer_position": "the requirement says 5",
}


@pytest.fixture
def product(tmp_path):
    """Every requirement rated medium: nothing is important until a test says so."""
    root = build_python_product(tmp_path / "product")
    _rate(root)
    return root


def _rate(root, **criticality):
    """Rate every requirement medium, except those named (REQ_0048="high")."""
    path = root / "docs/requirements/login.md"
    text = re.sub(r"criticality: \w+", "criticality: medium", path.read_text())
    for uid, rating in criticality.items():
        uid = uid.replace("_", "-")
        text = re.sub(
            rf"(uid: {uid}\n(?:.*\n)*?criticality: )medium", rf"\g<1>{rating}", text, count=1
        )
    path.write_text(text)
    commit_all(root, "ratings")
    import subprocess

    subprocess.run(["git", "-C", str(root), "branch", "-f", "main"], check=True)


def _classify(root, files, record=None):
    return classify(read_product_config(root), files, record, base="main")


def test_the_build_itself_calls_no_one(product):
    """A design, code, a unit test or a build file merges on the reviewer agent
    and the gates, whatever the requirements' ratings (FB-45)."""
    _rate(product, REQ_0048="high")
    write_code(product, "auth-service", "count-failures", sdoc="REQ-0048")
    write_unit_test(product, "auth-service", "count-failures")
    (product / "pyproject.toml").write_text("[project]\nname = 'p'\n")
    for files in (
        [unit_path("auth-service", "count-failures")],
        [unit_path("auth-service", "count-failures", test=True)],
        ["docs/design/auth-service.md"],
        ["pyproject.toml"],
        [".github/workflows/quality_gates.yml", ".framework"],  # checked by gates
    ):
        assert not _classify(product, files).needed, files


def test_the_software_tests_bring_the_results(product):
    _rate(product, REQ_0050="high")
    write_software_plan(product)
    write_software_test(product)
    review = _classify(product, [SOFTWARE_TEST])
    assert review.reasons == ("brings the results of software verification",)
    assert review.brief == ("the feature's results are ready for your approval",)
    assert review.proves == ("REQ-0049", "REQ-0050", "REQ-0053")
    assert review.tests == review.candidates == (SOFTWARE_TEST,)  # described for the person


def test_documentation_and_approved_inputs_call_no_one(product):
    (product / "NOTES.md").write_text("notes\n")
    files = ["NOTES.md", "docs/requirements/login.md", "docs/approvals/x.yaml"]
    assert not _classify(product, files).needed


def test_the_architecture_always_calls_a_person(product):
    review = _classify(product, ["docs/architecture/components.md"])
    assert review.reasons == ("changes the architecture (docs/architecture/)",)


def test_a_recorded_checkpoint_decision_calls_a_person(product):
    """FB-68: the person's approval on the host proves the decision is theirs."""
    decision = "docs/approvals/2026-10-30T090000Z-checkpoint-2-requirements.yaml"
    review = _classify(product, [decision])
    assert review.reasons == (f"records a checkpoint decision ({decision})",)
    assert not _classify(product, ["docs/approvals/2026-10-30T090000Z-stage-4-done.yaml"]).needed


def test_the_products_settings_call_a_person(product):
    review = _classify(product, ["qf.yaml", ".gitmodules"])
    assert review.reasons == ("changes the product's settings (.gitmodules, qf.yaml)",)


def test_a_gap_the_reviewer_agent_approved_is_a_question_of_what_is_wanted(product):
    gap = {"text": "The design does not say what happens after five failures.", "gap": True}
    told = {"text": "The credentials are checked.", "source": ["unit:check-credentials"]}
    story = {"design": "auth-service", "story": "A wrong password", "steps": [told]}
    story["steps"].append({**gap, "source": ["unit:count-failures"]})
    other = {**story, "design": "web-app"}  # a design this pull request does not change
    record = {"person": "none", "findings": [], "stories": [story, other]}
    review = _classify(product, ["docs/design/auth-service.md"], record)
    assert review.designs == ("auth-service",)
    assert review.gaps == (("auth-service", "A wrong password", gap["text"]),)
    assert review.reasons == ("the design leaves 1 question(s) open that no requirement answers",)


def test_the_reasons_in_one_short_line():
    brief = ("it changes the product's settings", "a test got weaker", "the agents disagree")
    assert headline(brief) == "it changes the product's settings; a test got weaker; 1 more"


def test_a_story_step_must_name_what_its_design_has(product):
    design = product / "docs/design/auth-service.md"
    design.write_text("- **D1 — failures are counted per account.**\n\n" + design.read_text())
    step = {"text": "The credentials are checked.", "source": []}
    story = {"design": "auth-service", "story": "A wrong password", "steps": [step]}
    step["source"] = [
        "message:check-credentials-to-count-failures",
        "unit:open-session",
        "decision:D1",
    ]
    assert unsourced(read_product_config(product), [story]) == []
    step["source"] = ["unit:send-email", "message:check-credentials-to-open-session", "decision:D2"]
    assert unsourced(read_product_config(product), [story]) == [
        "'A wrong password' step 1: unit:send-email is not in auth-service",
        "'A wrong password' step 1: decision:D2 is not in auth-service",
    ]


def _committed_test(product):
    path = unit_path("auth-service", "count-failures", test=True)
    write_unit_test(product, "auth-service", "count-failures")
    commit_all(product, "a test")
    import subprocess

    subprocess.run(["git", "-C", str(product), "branch", "-f", "main"], check=True)
    return path


def test_a_deleted_test_is_a_weakening(product):
    path = _committed_test(product)
    (product / path).unlink()
    (weakening,) = _classify(product, [path]).weakenings
    assert (weakening.file, weakening.now) == (path, "deleted")


def test_a_switched_off_test_is_a_weakening(product):
    path = _committed_test(product)
    text = (product / path).read_text()
    (product / path).write_text(text.replace("def test_", "@pytest.mark.skip\ndef test_"))
    (weakening,) = _classify(product, [path]).weakenings
    assert weakening.now == "switched off: @pytest.mark.skip"


def test_fewer_tests_in_a_file_is_a_weakening(product):
    path = _committed_test(product)
    (product / path).write_text((product / path).read_text() + "\n\ndef test_more():\n    pass\n")
    commit_all(product, "two tests")
    import subprocess

    subprocess.run(["git", "-C", str(product), "branch", "-f", "main"], check=True)
    write_unit_test(product, "auth-service", "count-failures")
    (weakening,) = _classify(product, [path]).weakenings
    assert weakening.now == "1 test(s) fewer"


def test_a_lowered_coverage_minimum_is_a_weakening(product):
    edit_plan(product, lambda plan: plan["unit"]["coverage"].update(minimum=10))
    review = _classify(product, ["docs/verification-plan.md"])
    (weakening,) = review.weakenings
    assert weakening.now == "unit coverage minimum 10" and review.needed


def test_a_finding_closed_without_a_change_calls_a_person(product):
    record = {"person": "none", "findings": [DISPUTE]}
    review = _classify(product, ["NOTES.md"], record)
    assert review.reasons == ("1 reviewer finding(s) closed without a change",)
    assert review.disputes == (DISPUTE,)


def test_the_reviewer_agent_may_ask_for_a_person(product):
    asked = {"person": {"condition": 4, "reason": "publishes posts"}, "findings": []}
    review = _classify(product, ["NOTES.md"], asked)
    assert review.request == asked["person"] and review.needed
