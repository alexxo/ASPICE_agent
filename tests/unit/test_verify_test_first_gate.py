"""gates/swe/verify_test_first_gate.py — tests first, red on their commit, unchanged with code."""

import re

import pytest
from product_builder import (
    build_python_product,
    commit_all,
    write_all_code,
    write_all_tests_and_stubs,
    write_code,
    write_stub,
    write_unit_test,
)

from gates.swe.verify_test_first_gate import GATE, check
from tools.read_product_config_tool import read_product_config


@pytest.fixture(autouse=True)
def _no_ci_base(monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)


def _rules(root, base=None):
    return sorted(f.rule for f in check(read_product_config(root), base=base))


def _red(tmp_path):
    """Stage 5 done: every unit's stub and test in one test-only commit."""
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    commit_all(root, "test: units of every component")
    return root


def test_gate_name_follows_the_convention():
    assert GATE == "verify_test_first_gate"


def test_before_any_test_every_unit_is_missing_its_stub_and_test(tmp_path):
    rules = _rules(build_python_product(tmp_path))
    assert set(rules) == {"MISSING_STUB", "MISSING_UNIT_TEST"}
    assert len(rules) == 8  # four units


def test_a_red_test_only_commit_passes(tmp_path):
    assert _rules(_red(tmp_path)) == []


def test_code_after_its_tests_passes(tmp_path):
    root = _red(tmp_path)
    write_all_code(root)
    commit_all(root, "feat: the units")
    assert _rules(root) == []


def test_a_test_that_passes_against_its_stub_is_reported(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    write_unit_test(root, "auth-service", "count-failures", assertion="run(1) == 0")
    commit_all(root, "test: units")
    assert _rules(root) == ["TEST_NOT_FAILING"]


def test_an_error_on_a_stub_counts_as_red(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    write_unit_test(root, "auth-service", "count-failures", assertion="run(1).bit_count() == 9")
    (root / "src" / "auth_service" / "count_failures.py").write_text(
        "# @unit[count-failures]\n\n\ndef run(value):\n    return None\n"
    )
    commit_all(root, "test: units")
    assert _rules(root) == []


def test_tests_that_do_not_run_are_reported(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    stack_file = root / "docs" / "architecture" / "stack.yaml"
    stack_file.write_text(stack_file.read_text().replace("build/unit.xml", "build/nowhere.xml", 1))
    commit_all(root, "test: units")
    assert "RED_RUN_WITHOUT_RESULTS" in _rules(root)


def test_code_committed_before_its_test_is_reported(tmp_path):
    root = build_python_product(tmp_path)
    write_code(root, "auth-service", "count-failures")
    commit_all(root, "feat: count failures first")
    write_all_tests_and_stubs(root)
    write_code(root, "auth-service", "count-failures")  # keep the real code, not a stub
    commit_all(root, "test: units")
    assert "CODE_BEFORE_TEST" in _rules(root)


def test_a_test_commit_that_changes_code_is_reported(tmp_path):
    root = _red(tmp_path)
    write_all_code(root)
    commit_all(root, "feat: the units")
    write_code(root, "web-app", "signin-form", sdoc="REQ-0049")
    write_unit_test(root, "web-app", "signin-form", assertion="run(2) == 3")
    commit_all(root, "test and code together")
    assert _rules(root) == ["TEST_CHANGED_WITH_CODE"]


def test_new_tests_with_changed_code_are_reported(tmp_path):
    root = _red(tmp_path)
    write_all_code(root)
    commit_all(root, "feat: the units")
    write_code(root, "web-app", "signin-form", sdoc="REQ-0049")
    write_unit_test(root, "web-app", "signin-form-extra")
    commit_all(root, "a new test with a code change")
    assert "CODE_IN_TEST_COMMIT" in _rules(root)


def test_a_weakened_test_alone_must_still_be_red(tmp_path):
    root = _red(tmp_path)
    write_all_code(root)
    commit_all(root, "feat: the units")
    write_unit_test(root, "auth-service", "open-session", assertion="run(1) is not None")
    commit_all(root, "test: loosen open-session")
    assert _rules(root) == ["TEST_NOT_FAILING"]


def test_an_uncommitted_test_is_reported(tmp_path):
    root = _red(tmp_path)
    write_unit_test(root, "auth-service", "count-failures", assertion="run(2) == 3")
    assert _rules(root) == ["TEST_NOT_COMMITTED"]


def test_commits_already_on_main_are_not_read_again(tmp_path):
    root = build_python_product(tmp_path, branch=None)
    write_code(root, "auth-service", "count-failures")
    commit_all(root, "legacy code on main")
    write_all_tests_and_stubs(root)
    write_code(root, "auth-service", "count-failures")
    commit_all(root, "legacy tests on main")
    assert _rules(root) == []  # on main, the range is empty


def test_an_explicit_base_sets_the_range(tmp_path):
    root = build_python_product(tmp_path, branch=None)
    write_stub(root, "web-app", "signin-form")
    write_code(root, "web-app", "signin-form")
    commit_all(root, "code first")
    first = _rules(root, base="HEAD~1")
    assert "CODE_BEFORE_TEST" in first


def test_outside_git_the_order_cannot_be_shown(tmp_path):
    root = _red(tmp_path)
    import shutil

    shutil.rmtree(root / ".git")
    assert _rules(root) == ["NOT_A_GIT_REPOSITORY"]


def test_a_commits_red_run_is_kept_and_not_run_again(tmp_path):
    root = _red(tmp_path)
    assert _rules(root) == []
    kept = list((root / ".qf" / "runs").glob("commit-*/suites-unit.json"))
    assert len(kept) == 1
    run_dir = kept[0].parent / "suites-unit" / "results"
    for result in run_dir.iterdir():  # what was kept now says every test passed
        result.write_text(re.sub(r"<failure.*?</failure>", "", result.read_text(), flags=re.S))
    assert _rules(root) == ["TEST_NOT_FAILING"] * 6  # read from what was kept


def test_a_test_fixed_in_a_later_test_only_commit_is_judged_as_fixed(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    write_unit_test(root, "auth-service", "count-failures", assertion="run(1) == 0")
    commit_all(root, "test: units, one passing on its stub")
    assert _rules(root) == ["TEST_NOT_FAILING"]
    write_unit_test(root, "auth-service", "count-failures")
    commit_all(root, "test: count-failures fixed")
    assert _rules(root) == []


def test_an_integration_test_changed_with_code_is_reported(tmp_path):
    from product_builder import (
        write_all_integration_tests,
        write_component_test,
        write_events_code,
    )

    root = _red(tmp_path)
    write_all_code(root)
    commit_all(root, "feat: units")
    write_all_integration_tests(root)
    commit_all(root, "test: components and flows")
    assert _rules(root) == []  # a test-only commit of integration tests needs no red run
    write_events_code(root)
    write_component_test(root, "web-app", assertion="run(1) is not None")
    commit_all(root, "feat: events, and a loosened component test")
    assert _rules(root) == ["TEST_CHANGED_WITH_CODE"]


def test_a_software_test_changed_with_code_is_reported(tmp_path):
    from product_builder import write_all_software_tests, write_e2e_test, write_events_code

    root = _red(tmp_path)
    write_all_code(root)
    commit_all(root, "feat: units")
    write_all_software_tests(root)
    commit_all(root, "test: requirements")
    assert _rules(root) == []  # a test-only commit of software tests needs no red run
    write_events_code(root)
    write_e2e_test(root, assertion="run(1) is not None")
    commit_all(root, "feat: events, and a loosened end-to-end test")
    assert _rules(root) == ["TEST_CHANGED_WITH_CODE"]


def test_an_uncommitted_software_test_is_reported(tmp_path):
    from product_builder import E2E_TEST, write_e2e_test

    root = _red(tmp_path)
    write_e2e_test(root)
    findings = check(read_product_config(root))
    assert [(f.rule, f.file) for f in findings] == [("TEST_NOT_COMMITTED", E2E_TEST)]
