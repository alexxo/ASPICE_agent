"""tools/write_validation_record_tool.py — the scenarios, the affected wishes, the record."""

import pytest
import yaml
from product_builder import (
    ALL_SCENARIOS,
    DEMO,
    SCENARIO_TESTS,
    build_releasable_product,
    commit_all,
    git_head,
    passed,
    propose_release,
    record_validation,
    tag_release,
    write_scenario_test,
)

from tools.read_product_config_tool import read_product_config
from tools.run_stack_commands_tool import read_stack
from tools.validate_contract_tool import validate
from tools.write_validation_record_tool import affected_wishes, main, scan_scenarios

RECORD = "validation/records/1.0.0.yaml"


@pytest.fixture
def product(tmp_path, monkeypatch):
    root, host = build_releasable_product(tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return root


def config(root):
    return read_product_config(root)


def record(root):
    return yaml.safe_load((root / RECORD).read_text())


def run(root, commit=None):
    return main(["--root", str(root), "--environment", "staging", "--commit", commit or "HEAD"])


def test_a_scenario_names_a_wish_and_is_automated_by_the_stack(product):
    (product / "validation/scenarios/conftest.py").write_text("import os\n")
    (product / "validation/scenarios/.drafts").mkdir()
    (product / "validation/scenarios/.drafts/test_x.py").write_text("# @wish[W-01]\n")
    found = scan_scenarios(config(product), read_stack(config(product)))
    assert [(s.path, s.automated, list(s.wishes)) for s in found] == [
        (DEMO, False, ["W-02"]),
        (SCENARIO_TESTS["W-03"], True, ["W-03"]),
        (SCENARIO_TESTS["W-01"], True, ["W-01"]),
    ]


def test_without_a_stack_every_scenario_is_run_by_hand(product):
    assert not any(s.automated for s in scan_scenarios(config(product), None))


def test_the_first_release_affects_every_wish(product):
    assert affected_wishes(config(product)) == {"W-01", "W-02", "W-03"}


def test_a_release_of_tests_only_affects_no_wish(product):
    tag_release(product, "1.0.0")
    write_scenario_test(product, "W-01")
    (product / "it").mkdir(exist_ok=True)
    (product / "it/test_more.py").write_text("def test_more():\n    assert True\n")
    commit_all(product, "test: more tests #3")
    assert affected_wishes(config(product)) == set()


def test_a_release_that_changes_a_requirement_affects_every_wish(product):
    tag_release(product, "1.0.0")
    folder = product / "docs/requirements"
    first = sorted(folder.glob("*.md"))[0]
    first.write_text(first.read_text() + "\n")
    commit_all(product, "docs: reword #3")
    assert affected_wishes(config(product)) == {"W-01", "W-02", "W-03"}


def test_nothing_is_recorded_without_a_proposed_release(product, capsys):
    assert run(product) == 2
    assert "Exactly one release must be proposed" in capsys.readouterr().err


def test_a_commit_that_does_not_exist_is_refused(product, capsys):
    propose_release(product)
    assert run(product, "0" * 40) == 2
    assert "is no commit" in capsys.readouterr().err


def test_the_record_holds_the_deployed_commit_and_the_automated_results(product, capsys):
    propose_release(product)
    write_scenario_test(product, "W-03", passes=False)
    commit_all(product, "test(validation): runtime fails #2")
    assert run(product) == 0
    written = record(product)
    assert validate(written, "validation") == []
    assert written["environment"] == {"name": "staging", "commit": git_head(product)}
    assert written["results"] == [
        {"scenario": SCENARIO_TESTS["W-03"], "technique": "acceptance test", "result": "fail"},
        {"scenario": SCENARIO_TESTS["W-01"], "technique": "acceptance test", "result": "pass"},
    ]
    assert f"Enter the result of {DEMO}" in capsys.readouterr().err


def test_the_results_entered_by_hand_stay_for_the_same_deployment(product):
    propose_release(product)
    record_validation(product, passed(*ALL_SCENARIOS), commit=git_head(product))
    deployed = record(product)["environment"]["commit"]
    assert run(product, deployed) == 0
    assert DEMO in [r["scenario"] for r in record(product)["results"]]
    assert run(product, "HEAD") == 0  # a new deployment: the record has moved on
    assert DEMO not in [r["scenario"] for r in record(product)["results"]]
