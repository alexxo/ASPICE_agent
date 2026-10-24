"""tools/classify_pull_request_tool.py — a person reviews what is important or risky."""

import re

import pytest
from product_builder import (
    build_python_product,
    commit_all,
    edit_plan,
    unit_path,
    write_code,
    write_unit_test,
)

from tools.classify_pull_request_tool import classify
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


def test_a_change_to_a_medium_functional_requirement_needs_no_person(product):
    write_code(product, "auth-service", "count-failures", sdoc="REQ-0048")
    assert not _classify(product, [unit_path("auth-service", "count-failures")]).needed


def test_a_requirement_rated_high_at_checkpoint_2_calls_a_person(tmp_path):
    root = build_python_product(tmp_path / "product")
    _rate(root, REQ_0048="high")
    write_code(root, "auth-service", "count-failures", sdoc="REQ-0048")
    review = _classify(root, [unit_path("auth-service", "count-failures")])
    assert review.reasons == ("touches REQ-0048 (criticality high)",)


def test_code_without_its_requirement_takes_its_components(product):
    """auth-service meets REQ-0047, of kind security: coarse, but none missed."""
    write_code(product, "auth-service", "count-failures")
    review = _classify(product, [unit_path("auth-service", "count-failures")])
    assert review.reasons == ("touches REQ-0047 (security)",)


def test_a_component_with_an_external_interface_crosses_a_trust_boundary(product):
    write_code(product, "web-app", "signin-form", sdoc="REQ-0053")
    review = _classify(product, [unit_path("web-app", "signin-form")])
    assert review.reasons == ("crosses a trust boundary: user → web-app",)


def test_a_file_that_traces_to_nothing_touches_everything(product):
    (product / "pyproject.toml").write_text("[project]\nname = 'p'\n")
    review = _classify(product, ["pyproject.toml"])
    assert review.needed and "pyproject.toml" in review.reasons[0]


def test_documentation_and_approved_inputs_call_no_one(product):
    (product / "NOTES.md").write_text("notes\n")
    files = ["NOTES.md", "docs/requirements/login.md", "docs/approvals/x.yaml"]
    assert not _classify(product, files).needed


def test_the_architecture_always_calls_a_person(product):
    review = _classify(product, ["docs/architecture/components.md"])
    assert review.reasons == ("changes the architecture (docs/architecture/)",)


def test_a_detailed_design_is_its_components(product):
    review = _classify(product, ["docs/design/auth-service.md"])
    assert review.designs == ("auth-service",)
    assert review.reasons == ("touches REQ-0047 (security)",)


def test_the_tests_to_describe_are_those_of_what_made_it_important(product):
    write_unit_test(product, "auth-service", "count-failures")
    write_unit_test(product, "web-app", "signin-form")
    files = [unit_path("auth-service", "count-failures", test=True)]
    files += [unit_path("web-app", "signin-form", test=True)]
    review = _classify(product, files)
    assert set(review.tests) == set(files)  # both: security and a trust boundary
    assert review.requirements[files[0]] == ["REQ-0047", "REQ-0048", "REQ-0050", "REQ-0051"]


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


def test_the_reviewer_agent_may_ask_for_a_person_never_cancel_one(product):
    asked = {"person": {"condition": 4, "reason": "publishes posts"}, "findings": []}
    assert _classify(product, ["NOTES.md"], asked).request == asked["person"]
    write_code(product, "web-app", "signin-form")
    files = [unit_path("web-app", "signin-form")]
    assert _classify(product, files, {"person": "none", "findings": []}).needed
