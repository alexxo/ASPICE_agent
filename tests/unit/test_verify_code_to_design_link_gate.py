"""gates/swe/verify_code_to_design_link_gate.py — code and tests ↔ the detailed design."""

from product_builder import (
    build_python_product,
    write_all_code,
    write_all_tests_and_stubs,
    write_code,
)

from gates.swe.verify_code_to_design_link_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _built(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    return root


def test_gate_name_follows_the_convention():
    assert GATE == "verify_code_to_design_link_gate"


def test_every_unit_implemented_and_marked_passes(tmp_path):
    assert _rules(_built(tmp_path)) == []


def test_a_unit_without_code_is_reported(tmp_path):
    root = _built(tmp_path)
    (root / "src" / "web_app" / "signin_form.py").unlink()
    assert _rules(root) == ["UNIMPLEMENTED_UNIT"]


def test_a_code_file_without_a_marker_is_reported(tmp_path):
    root = _built(tmp_path)
    (root / "src" / "auth_service" / "helpers.py").write_text("X = 1\n")
    assert _rules(root) == ["MISSING_UNIT_MARKER"]


def test_the_composition_root_needs_no_unit_marker(tmp_path):
    """FB-50: the architecture names it; it wires the units and implements none."""
    root = _built(tmp_path)
    (root / "src" / "WebappApp.py").write_text("def main():\n    pass\n")
    assert _rules(root) == []


def test_a_composition_root_in_a_package_needs_no_marker_outside_its_component(tmp_path):
    root = _built(tmp_path)
    for doc in (root / "docs" / "architecture").glob("*.md"):
        doc.write_text(doc.read_text().replace("WebappApp.main", "shop.__main__.main"))
    (root / "src" / "shop").mkdir()
    (root / "src" / "shop" / "__main__.py").write_text("def main():\n    pass\n")
    (root / "src" / "shop" / "other.py").write_text("X = 1\n")
    assert _rules(root) == ["MISSING_UNIT_MARKER"]  # other.py alone


def test_a_package_init_with_a_docstring_alone_needs_no_marker(tmp_path):
    root = _built(tmp_path)
    (root / "src" / "auth_service" / "__init__.py").write_text('"""The auth service."""\n')
    (root / "src" / "web_app" / "__init__.py").write_text("")
    assert _rules(root) == []
    (root / "src" / "web_app" / "__init__.py").write_text("from os import path\n")
    assert _rules(root) == ["MISSING_UNIT_MARKER"]


def test_a_marker_naming_no_unit_is_reported_in_code_and_tests(tmp_path):
    root = _built(tmp_path)
    (root / "src" / "auth_service" / "extra.py").write_text("# @unit[ghost]\n")
    (root / "src" / "auth_service" / "test_extra.py").write_text("# @unit[ghost]\n")
    assert _rules(root) == ["UNKNOWN_UNIT", "UNKNOWN_UNIT"]


def test_a_unit_outside_its_component_folder_is_reported(tmp_path):
    root = _built(tmp_path)
    moved = root / "src" / "utils" / "count_failures.py"
    moved.parent.mkdir()
    (root / "src" / "auth_service" / "count_failures.py").rename(moved)
    assert _rules(root) == ["UNIT_OUTSIDE_COMPONENT"]


def test_a_requirement_marker_naming_no_requirement_is_reported(tmp_path):
    root = _built(tmp_path)
    write_code(root, "auth-service", "count-failures", sdoc="REQ-9999")
    assert _rules(root) == ["UNKNOWN_REQUIREMENT"]
    write_code(root, "auth-service", "count-failures", sdoc="REQ-0047")
    assert _rules(root) == []
