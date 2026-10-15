"""tools/select_tests_tool.py — on a change, only the tests traced to it run."""

import copy
import subprocess

import pytest
import yaml
from product_builder import (
    PLAN,
    build_python_product,
    commit_all,
    python_stack,
    write_all_code,
    write_all_integration_tests,
    write_all_software_tests,
    write_all_tests_and_stubs,
    write_code,
)

from gates.swe.check_stack_commands_gate import check as check_stack_commands
from gates.swe.verify_tests_to_requirements_link_gate import check as check_unit_links
from tools.read_product_config_tool import read_product_config
from tools.run_stack_commands_tool import run_command
from tools.select_tests_tool import Selection, select, tests_argument, trace

COUNT_FAILURES = "src/auth_service/count_failures.py"
COUNT_FAILURES_TEST = "src/auth_service/test_count_failures.py"


def _selected_stack() -> dict:
    stack = python_stack()
    unit = stack["suites"]["unit"]
    unit["run_selected"] = unit["run"].removesuffix(" src") + " {tests}"
    unit["selected_form"] = "paths"
    return stack


def _plan(on_change: str = "selected", minimum: int = 50) -> dict:
    plan = copy.deepcopy(PLAN)
    plan["unit"]["on_change"] = on_change
    plan["unit"]["coverage"]["minimum"] = minimum
    return plan


@pytest.fixture
def product(tmp_path, monkeypatch):
    """Every unit built and tested on main; the work continues on a feature branch."""
    monkeypatch.delenv("QF_BASE", raising=False)
    monkeypatch.delenv("QF_RUN", raising=False)
    root = build_python_product(tmp_path, plan=_plan(), stack=_selected_stack(), branch=None)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    commit_all(root, "every unit built")
    subprocess.run(["git", "-C", str(root), "checkout", "-q", "-b", "feature/x"], check=True)
    return root


def _unit(root) -> Selection:
    config = read_product_config(root)
    return select(config, _selected_stack(), "unit")


def _change(root, relative: str, text: str | None = None) -> None:
    """Change a file: a comment on top, or the given text at the end."""
    path = root / relative
    old = path.read_text()
    path.write_text("# changed\n" + old if text is None else old + text)


def test_a_changed_unit_selects_its_own_tests(product):
    _change(product, COUNT_FAILURES)

    chosen = _unit(product)

    assert chosen.selected
    assert list(chosen.tests) == [COUNT_FAILURES_TEST]
    assert chosen.tests[COUNT_FAILURES_TEST] == ["@unit[count-failures] is in the change"]


def test_committed_changes_since_the_base_count(product):
    _change(product, COUNT_FAILURES)
    commit_all(product, "change count-failures")

    assert list(_unit(product).tests) == [COUNT_FAILURES_TEST]


def test_a_changed_test_selects_itself(product):
    _change(product, COUNT_FAILURES_TEST)

    reasons = _unit(product).tests[COUNT_FAILURES_TEST]

    assert f"{COUNT_FAILURES_TEST} changed" in reasons


def test_the_scope_grows_along_the_architecture(product):
    _change(product, COUNT_FAILURES)

    scope = trace(read_product_config(product), _selected_stack()).scope

    assert scope.units == {"count-failures"}
    assert {"auth-service", "web-app"} <= scope.components  # joined by signin-request
    assert "REQ-0047" in scope.requirements  # met by the auth service
    assert "login" in scope.flows  # the auth service takes part in it


@pytest.mark.parametrize(
    ("path", "why"),
    [("README.md", "traces to no unit"), ("src/auth_service/helpers.py", "names no unit")],
)
def test_a_change_that_traces_to_nothing_runs_every_test(product, path, why):
    (product / path).parent.mkdir(parents=True, exist_ok=True)
    (product / path).write_text("plain\n")

    chosen = _unit(product)

    assert not chosen.selected
    assert why in chosen.full


def test_a_deleted_file_runs_every_test(product):
    (product / COUNT_FAILURES).unlink()

    assert "traces to no unit" in _unit(product).full


def test_no_change_runs_every_test(product):
    assert _unit(product).full == "nothing changed since the base"


def test_a_proposed_release_runs_every_test(product):
    _change(product, COUNT_FAILURES)
    (product / "releases").mkdir()
    (product / "releases" / "1.0.0.yaml").write_text("version: 1.0.0\n")

    assert "a release is proposed" in _unit(product).full


def test_qf_run_full_runs_every_test(product, monkeypatch):
    _change(product, COUNT_FAILURES)
    monkeypatch.setenv("QF_RUN", "full")

    assert "QF_RUN=full" in _unit(product).full


def test_a_plan_saying_all_runs_every_test(tmp_path):
    root = build_python_product(tmp_path, plan=_plan("all"), stack=_selected_stack())
    _change(root, "qf.yaml")

    assert "on_change: selected" in _unit(root).full


def test_a_suite_without_run_selected_runs_every_test(product):
    _change(product, COUNT_FAILURES)
    config = read_product_config(product)

    chosen = select(config, python_stack(), "unit")

    assert chosen.full == "suites.unit declares no run_selected"


def test_suites_outside_the_three_levels_run_every_test(product):
    chosen = select(read_product_config(product), _selected_stack(), "bench")

    assert chosen.full == "the bench suite always runs in full"


def test_the_tests_are_listed_as_paths_or_names():
    chosen = Selection("unit", None, {"src/a/test_b.py": [], "src/a/test_c.py": []})

    assert tests_argument(chosen, {"selected_form": "paths"}) == "src/a/test_b.py src/a/test_c.py"
    assert tests_argument(chosen, {"selected_form": "names"}) == "test_b,test_c"


def test_the_suite_runs_only_the_selected_tests(product):
    _change(product, COUNT_FAILURES)
    config = read_product_config(product)

    run = run_command(config, "suites", "unit", _selected_stack()["suites"]["unit"])

    assert run.exit_code == 0, run.output
    assert not run.full
    assert "1 passed" in run.output
    assert list(run.selection["tests"]) == [COUNT_FAILURES_TEST]


def test_a_change_no_test_is_traced_to_runs_nothing(product):
    write_code(product, "auth-service", "orphan")  # a unit no test names

    run = run_command(
        read_product_config(product), "suites", "unit", _selected_stack()["suites"]["unit"]
    )

    assert run.ran_nothing
    assert run.results == []
    assert check_stack_commands(read_product_config(product)) == []


def test_a_selected_run_judges_only_the_units_in_its_scope(product):
    (product / "src/web_app/test_signin_form.py").unlink()
    (product / "src/web_app/test_signin_form_security.py").unlink()
    commit_all(product, "the web app loses its tests")  # deleted: every test runs
    rules_full = sorted(f.rule for f in check_unit_links(read_product_config(product)))
    subprocess.run(["git", "-C", str(product), "branch", "-f", "main"], check=True)
    _change(product, COUNT_FAILURES)

    rules_selected = sorted(f.rule for f in check_unit_links(read_product_config(product)))

    assert rules_full == ["UNTESTED_UNIT"]
    assert rules_selected == []


def test_a_failing_selected_test_is_reported(product):
    _change(product, COUNT_FAILURES, "\n\ndef run(value):\n    return 0\n")

    rules = sorted(f.rule for f in check_unit_links(read_product_config(product)))

    assert rules == ["FAILED_TEST", "UNTESTED_UNIT"]


def test_coverage_is_judged_on_a_full_run_only(product):
    """A selected run that writes no coverage at all is not judged on coverage."""
    stack = _selected_stack()
    unit = stack["suites"]["unit"]
    unit["run_selected"] = unit["run_selected"].replace(
        " --cov=src --cov-report=xml:build/coverage.xml", ""
    )
    stack_file = product / "docs" / "architecture" / "stack.yaml"
    stack_file.write_text(yaml.safe_dump(stack, sort_keys=False))
    commit_all(product, "the selected unit run measures no coverage")
    subprocess.run(["git", "-C", str(product), "branch", "-f", "main"], check=True)
    _change(product, COUNT_FAILURES)
    config = read_product_config(product)

    run = run_command(config, "suites", "unit", unit)

    assert not run.full and run.coverage is None
    assert check_stack_commands(config) == []


def test_the_plan_requires_on_change():
    plan = yaml.safe_load(yaml.safe_dump(PLAN))
    del plan["unit"]["on_change"]

    from tools.validate_contract_tool import validate

    assert any("on_change" in v.message for v in validate(plan, "verification_plan"))


def test_the_integration_and_software_levels_follow_the_scope(tmp_path, monkeypatch):
    """A changed auth-service unit selects the component tests of the auth service
    and its neighbour, the login flow, and the software tests of the requirements
    the two components meet."""
    monkeypatch.delenv("QF_BASE", raising=False)
    monkeypatch.delenv("QF_RUN", raising=False)
    stack = _selected_stack()
    for suite in ("integration", "software"):
        entry = stack["suites"][suite]
        entry["run_selected"] = entry["run"].rsplit(" ", 1)[0] + " {tests}"
        entry["selected_form"] = "paths"
    root = build_python_product(tmp_path, plan=_plan(), stack=stack, branch=None)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    write_all_integration_tests(root)
    write_all_software_tests(root)
    plan_file = root / "docs" / "verification-plan.md"
    plan_file.write_text(plan_file.read_text().replace("on_change: all", "on_change: selected"))
    commit_all(root, "every level built")
    subprocess.run(["git", "-C", str(root), "checkout", "-q", "-b", "feature/x"], check=True)
    _change(root, COUNT_FAILURES)
    config = read_product_config(root)
    traced = trace(config, stack)

    integration = select(config, stack, "integration", traced)
    software = select(config, stack, "software", traced)

    assert integration.selected and software.selected
    assert set(integration.tests) == {
        "it/test_auth_service_component.py",
        "it/test_web_app_component.py",
        "it/test_login_flow.py",
    }
    assert "@flow[login] is in the change" in integration.tests["it/test_login_flow.py"]
    assert software.tests
    assert all(r.startswith("@sdoc[") for rs in software.tests.values() for r in rs)
