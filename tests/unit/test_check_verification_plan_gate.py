"""gates/swe/check_verification_plan_gate.py — one complete verification plan."""

import copy

from product_builder import PLAN, build_python_product

from gates.swe.check_verification_plan_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _plan_file(root):
    return root / "docs" / "verification-plan.md"


def test_gate_name_follows_the_convention():
    assert GATE == "check_verification_plan_gate"


def test_a_complete_plan_passes(tmp_path):
    assert _rules(build_python_product(tmp_path)) == []


def test_no_plan_is_reported(tmp_path):
    assert _rules(build_python_product(tmp_path, plan=None)) == ["MISSING_VERIFICATION_PLAN"]


def test_a_file_without_a_block_is_reported(tmp_path):
    root = build_python_product(tmp_path)
    _plan_file(root).write_text("# Verification plan\n\nTo do.\n")
    assert _rules(root) == ["MISSING_VERIFICATION_PLAN"]


def test_two_blocks_are_reported(tmp_path):
    root = build_python_product(tmp_path)
    text = _plan_file(root).read_text()
    _plan_file(root).write_text(text + "\n" + text)
    assert _rules(root) == ["MULTIPLE_PLANS"]


def test_an_unreadable_block_is_reported(tmp_path):
    root = build_python_product(tmp_path)
    _plan_file(root).write_text("```yaml verification_plan\nunit: [\n```\n")
    assert _rules(root) == ["UNREADABLE_BLOCK"]


def test_a_plan_without_coverage_breaks_its_contract(tmp_path):
    plan = copy.deepcopy(PLAN)
    del plan["unit"]["coverage"]
    assert _rules(build_python_product(tmp_path, plan=plan)) == ["SCHEMA_VIOLATION"]


def test_a_suite_whose_tool_is_no_test_runner_is_reported(tmp_path):
    plan = copy.deepcopy(PLAN)
    plan["unit"]["suites"]["unit"]["tool"] = "nose"
    findings = check(read_product_config(build_python_product(tmp_path, plan=plan)))
    assert [f.rule for f in findings] == ["UNKNOWN_TOOL"]
    assert "'nose'" in findings[0].message


def test_a_suite_a_requirement_names_but_its_section_lacks_is_reported(tmp_path):
    from product_builder import MEASURED_REQUIREMENTS, edit_plan, write_software_plan

    root = build_python_product(tmp_path)
    write_software_plan(root)
    edit_plan(root, lambda p: p["software"]["suites"].pop("bench"))
    findings = check(read_product_config(root))
    assert [f.rule for f in findings] == ["UNKNOWN_INSTRUMENT"] * len(MEASURED_REQUIREMENTS)
    assert all(f.file == "docs/requirements/login.md" for f in findings)


def test_a_suite_is_required_only_once_its_section_exists(tmp_path):
    """The measured requirements name bench, a software-level suite: before the
    bridge tester writes the software section, nothing is missing."""
    assert _rules(build_python_product(tmp_path)) == []


# ── the integration section (stage 7) ──────────────────────────────────────


def _with_integration(tmp_path, change=None):
    from product_builder import (
        INTEGRATION_PLAN,
        write_all_integration_tests,
        write_integration_plan,
    )

    root = build_python_product(tmp_path)
    write_all_integration_tests(root)
    if change is not None:
        integration = copy.deepcopy(INTEGRATION_PLAN)
        change(integration)
        block = {**copy.deepcopy(PLAN), "integration": integration}
        import yaml

        text = yaml.safe_dump(block, sort_keys=False)
        _plan_file(root).write_text(f"```yaml verification_plan\n{text}```\n")
    else:
        write_integration_plan(root)
    return root


def test_a_complete_integration_section_passes(tmp_path):
    assert _rules(_with_integration(tmp_path)) == []


def test_integration_tests_without_the_section_are_reported(tmp_path):
    from product_builder import write_component_test

    root = build_python_product(tmp_path)
    write_component_test(root, "web-app")
    assert _rules(root) == ["MISSING_INTEGRATION_SECTION"]


def test_an_order_naming_no_component_is_reported(tmp_path):
    root = _with_integration(tmp_path, lambda i: i["order"][0]["components"].append("mailer"))
    assert _rules(root) == ["UNKNOWN_COMPONENT"]


def test_a_component_in_no_step_is_reported(tmp_path):
    root = _with_integration(tmp_path, lambda i: i["order"].pop())
    assert _rules(root) == ["UNSCHEDULED_COMPONENT"]


def test_software_tests_without_the_section_are_reported(tmp_path):
    from product_builder import write_software_test

    root = build_python_product(tmp_path)
    write_software_test(root)
    assert _rules(root) == ["MISSING_SOFTWARE_SECTION"]


def test_a_complete_software_section_passes(tmp_path):
    from product_builder import write_software_plan, write_software_test

    root = build_python_product(tmp_path)
    write_software_plan(root)
    write_software_test(root)
    assert _rules(root) == []


# ── the validation section (stage 11) ──────────────────────────────────────


def _with_scenarios(tmp_path, plan=True):
    from product_builder import SCENARIO_TESTS, write_demo, write_scenario_test

    root = build_python_product(tmp_path)
    for wish in SCENARIO_TESTS:
        write_scenario_test(root, wish)
    write_demo(root)
    if plan:
        from product_builder import write_validation_plan

        write_validation_plan(root)
    return root


def test_a_plan_listing_every_scenario_passes(tmp_path):
    assert _rules(_with_scenarios(tmp_path)) == []


def test_scenarios_without_a_validation_section_are_reported(tmp_path):
    assert _rules(_with_scenarios(tmp_path, plan=False)) == ["MISSING_VALIDATION_SECTION"]


def test_a_scenario_the_plan_does_not_list_is_reported(tmp_path):
    root = _with_scenarios(tmp_path)
    (root / "validation/scenarios/trial-use.md").write_text("@wish[W-01] a week of real use\n")
    findings = check(read_product_config(root))
    assert [(f.rule, f.file) for f in findings] == [
        ("UNSELECTED_SCENARIO", "validation/scenarios/trial-use.md")
    ]


def test_a_listed_scenario_that_is_none_is_reported(tmp_path):
    from product_builder import DEMO

    root = _with_scenarios(tmp_path)
    (root / DEMO).write_text("The demo lost its wish marker.\n")
    assert _rules(root) == ["UNKNOWN_SCENARIO"]


def test_a_helper_naming_no_wish_needs_no_entry(tmp_path):
    root = _with_scenarios(tmp_path)
    (root / "validation/scenarios/conftest.py").write_text("import os\n")
    assert _rules(root) == []
