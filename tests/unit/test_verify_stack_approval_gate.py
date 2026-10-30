"""gates/swe/verify_stack_approval_gate.py — the stack approved before components are designed."""

from product_builder import STACK, approve_checkpoint, build_product

from gates.swe.verify_stack_approval_gate import GATE, check
from tools.read_approvals_tool import subject_files
from tools.read_product_config_tool import read_product_config


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _approve(root):
    approve_checkpoint(root, 3)


def test_gate_name_follows_the_convention():
    assert GATE == "verify_stack_approval_gate"


def test_the_approval_covers_the_stack_and_its_decision_record(tmp_path):
    root = build_product(tmp_path, stack=STACK, git=False)
    names = [f.name for f in subject_files(read_product_config(root), "stack")]
    assert names == ["stack.yaml", "0001-java-for-the-auth-service.md"]


def test_without_components_nothing_has_to_be_approved_yet(tmp_path):
    root = build_product(tmp_path, stack=STACK, git=False)
    (root / "docs/architecture/auth-flow.md").unlink()
    assert _rules(root) == []


def test_components_after_a_current_approval_pass(tmp_path):
    root = build_product(tmp_path, stack=STACK)
    _approve(root)
    assert _rules(root) == []


def test_components_without_an_approval_are_reported(tmp_path):
    assert _rules(build_product(tmp_path, stack=STACK)) == ["MISSING_APPROVAL"]


def test_a_changed_stack_makes_the_approval_outdated(tmp_path):
    root = build_product(tmp_path, stack=STACK)
    _approve(root)
    stack = root / "docs/architecture/stack.yaml"
    stack.write_text(stack.read_text().replace("'21'", "'25'"))
    assert _rules(root) == ["APPROVAL_OUTDATED"]
