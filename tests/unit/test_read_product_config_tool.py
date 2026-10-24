"""tools/read_product_config_tool.py — reads and validates the product's qf.yaml."""

import shutil

import pytest

from tools.read_product_config_tool import ConfigError, read_product_config


@pytest.fixture
def product(tmp_path, repo_root):
    shutil.copy(repo_root / "contracts/examples/qf/valid/qf.yaml", tmp_path / "qf.yaml")
    return tmp_path


def test_paths_resolve_under_the_product_root(product):
    config = read_product_config(product)
    assert config.requirements_dir == product / "docs/requirements"
    assert config.glossary_file == product / "docs/glossary.md"
    assert config.wishes_file == product / "docs/wishes.md"
    assert config.diagrams_dir == product / "docs/diagrams"
    assert config.approvals_dir == product / "docs/approvals"
    assert config.architecture_dir == product / "docs/architecture"
    assert config.decisions_dir == product / "docs/decisions"
    assert config.stack_file == product / "docs/architecture/stack.yaml"
    assert config.detailed_design_dir == product / "docs/design"
    assert config.code_dir == product / "src"
    assert config.verification_plan_file == product / "docs/verification-plan.md"
    assert config.env_variables_file == product / "docs/configuration.md"
    assert config.integration_tests_dir == product / "it"
    assert config.software_tests_dir == product / "st"
    assert config.observability_dir == product / "observability"
    assert config.framework_dir == product / ".framework"
    assert config.ci_file == product / ".github/workflows/quality_gates.yml"
    assert config.framework_feedback_file == product / "FRAMEWORK_FEEDBACK.md"
    assert config.releases_dir == product / "releases"
    assert config.validation_scenarios_dir == product / "validation/scenarios"
    assert config.validation_records_dir == product / "validation/records"


def test_the_review_section_is_available(product):
    config = read_product_config(product)
    assert config.review_agents == ("qf-reviewer-bot",)
    assert config.review_people == ("lead-bob",)


def test_the_issue_rules_are_available(product):
    config = read_product_config(product)
    assert (config.urgent_approvers, config.escalate_after_days) == (("lead-bob",), 30)
    assert config.change_approvers == ("lead-bob",)


def test_the_configuration_items_are_available(product):
    config = read_product_config(product)
    assert config.config_items == ("docs/runbooks",)


def test_slots_are_available(product):
    slots = read_product_config(product).slots
    assert slots["create_requirements_plugin"] == "quality-framework/derive_requirements_plugin"


def test_relative_gives_the_repository_path(product):
    config = read_product_config(product)
    assert config.relative(product / "docs/glossary.md") == "docs/glossary.md"


def test_missing_qf_yaml_is_an_error(tmp_path):
    with pytest.raises(ConfigError) as err:
        read_product_config(tmp_path)
    assert err.value.rule == "MISSING_CONFIG"


def test_unreadable_qf_yaml_gives_the_line(product):
    (product / "qf.yaml").write_text("contract: qf.v1\npaths: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError) as err:
        read_product_config(product)
    assert (err.value.rule, err.value.line) == ("INVALID_CONFIG", 2)


def test_qf_yaml_breaking_its_contract_is_an_error(product):
    text = (product / "qf.yaml").read_text().replace("  wishes_file: docs/wishes.md\n", "")
    (product / "qf.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError) as err:
        read_product_config(product)
    assert err.value.rule == "INVALID_CONFIG"
    assert "wishes_file" in err.value.message


def test_an_error_becomes_a_finding(tmp_path):
    with pytest.raises(ConfigError) as err:
        read_product_config(tmp_path)
    finding = err.value.to_finding()
    assert (finding.rule, finding.file) == ("MISSING_CONFIG", "qf.yaml")
