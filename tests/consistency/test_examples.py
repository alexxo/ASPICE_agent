"""Layer 2 — the example product is a valid product at the start of SWE.1.

Its configuration and approval follow their contracts, its diagrams read
without a problem, its checkpoint-1 approval matches the current diagram files,
and the scripted plugin output marked "correct" passes every SWE.1 gate.
"""

import hashlib
import shutil

import pytest

from adapters.read_archify_diagram_adapter import read_archify_diagrams
from gates.swe import (
    check_glossary_gate,
    check_requirements_contract_gate,
    verify_requirements_to_diagram_link_gate,
)
from tools.read_product_config_tool import read_product_config
from tools.read_yaml_blocks_tool import read_yaml_file
from tools.validate_contract_tool import validate

pytestmark = pytest.mark.layer2

GATES = [
    check_requirements_contract_gate,
    check_glossary_gate,
    verify_requirements_to_diagram_link_gate,
]
OUTPUTS = "tests/scenarios/plugin_outputs/requirements"


@pytest.fixture
def example(repo_root):
    return repo_root / "examples" / "login-product"


def test_configuration_is_valid(example):
    config = read_product_config(example)
    assert config.slots["create_diagram_plugin"] == "archify"


def test_diagrams_read_without_problems(example):
    results = read_archify_diagrams(example / "docs" / "diagrams", example)
    assert len(results) == 2
    assert all(r.diagram and not r.problems for _, r in results)


def test_checkpoint_1_approval_matches_the_diagrams(example):
    (approval,) = sorted((example / "docs" / "approvals").glob("*-checkpoint-1-*.yaml"))
    data = read_yaml_file(approval)
    assert validate(data, "approval") == []
    for item in data["subject"]:
        digest = hashlib.sha256((example / item["path"]).read_bytes()).hexdigest()
        assert digest == item["sha256"], f"{item['path']} changed since it was approved"


def test_every_framework_method_the_example_names_exists(example, repo_root):
    """A quality-framework/<method> slot must name a method this framework ships."""
    for slot in read_product_config(example).slots.values():
        plugin, _, skill = slot.partition("/")
        if plugin == "quality-framework":
            assert list(repo_root.glob(f"plugins/*/{skill}/SKILL.md")), f"{slot} is not shipped"


def test_correct_plugin_output_passes_every_gate(example, repo_root, tmp_path):
    product = tmp_path / "product"
    shutil.copytree(example, product)
    (product / "docs/requirements").mkdir(exist_ok=True)  # git keeps no empty directory
    shutil.copy(
        repo_root / OUTPUTS / "correct" / "login.md", product / "docs/requirements/login.md"
    )
    config = read_product_config(product)
    for gate in GATES:
        assert gate.check(config) == [], gate.GATE


@pytest.mark.parametrize("output", ["broken", "stuck"])
def test_failing_plugin_outputs_fail(example, repo_root, tmp_path, output):
    product = tmp_path / "product"
    shutil.copytree(example, product)
    (product / "docs/requirements").mkdir(exist_ok=True)  # git keeps no empty directory
    shutil.copy(repo_root / OUTPUTS / output / "login.md", product / "docs/requirements/login.md")
    config = read_product_config(product)
    assert any(gate.check(config) for gate in GATES)
