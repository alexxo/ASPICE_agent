"""tools/read_unit_markers_tool.py — unit and requirement markers in code and tests."""

import pytest
from product_builder import build_python_product, write_code, write_unit_test

from tools.read_product_config_tool import read_product_config
from tools.read_unit_markers_tool import (
    classify,
    design_units,
    glob_match,
    in_component_folder,
    markers,
    scan_sources,
)

STACK = {"code_files": ["**/*.java"], "test_files": ["**/*Test.java"]}


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("a.py", "**/*.py", True),
        ("x/y/a.py", "**/*.py", True),
        ("x/y/a.pyc", "**/*.py", False),
        ("x/test_a.py", "**/test_*.py", True),
        ("x/a_test.py", "**/test_*.py", False),
        ("main/java/A.java", "main/**/*.java", True),
        ("test/java/A.java", "main/**/*.java", False),
        ("a.py", "*.py", True),
        ("x/a.py", "*.py", False),
    ],
)
def test_glob_patterns_span_folders_only_with_two_stars(path, pattern, expected):
    assert glob_match(path, [pattern]) is expected


def test_a_test_file_is_a_test_even_though_it_also_matches_code():
    assert classify("com/acme/CountFailuresTest.java", STACK) == "test"
    assert classify("com/acme/CountFailures.java", STACK) == "code"
    assert classify("com/acme/application.yaml", STACK) is None


def test_markers_come_with_their_first_line():
    text = "// header\n// @unit[count-failures] @sdoc[REQ-0047]\nx // @unit[count-failures]\n"
    units, reqs = markers(text)
    assert units == {"count-failures": 2}
    assert reqs == {"REQ-0047": 2}


def test_a_component_folder_may_use_underscores():
    assert in_component_folder("src/main/java/com/acme/auth_service/A.java", "auth-service")
    assert in_component_folder("src/auth-service/a.py", "auth-service")
    assert not in_component_folder("src/utils/A.java", "auth-service")
    assert not in_component_folder("auth_service.py", "auth-service")


def test_design_units_name_their_component_and_design_file(tmp_path):
    config = read_product_config(build_python_product(tmp_path))
    units = design_units(config)
    assert units["count-failures"] == ("auth-service", "docs/design/auth-service.md")
    assert units["signin-form"] == ("web-app", "docs/design/web-app.md")


def test_scan_finds_code_and_tests_with_their_markers(tmp_path):
    root = build_python_product(tmp_path)
    write_code(root, "auth-service", "count-failures", sdoc="REQ-0047")
    write_unit_test(root, "auth-service", "count-failures")
    (root / "src" / "notes.txt").write_text("@unit[ignored]")
    config = read_product_config(root)
    from tools.run_stack_commands_tool import read_stack

    found = {s.path: s for s in scan_sources(config, read_stack(config))}
    assert set(found) == {
        "src/auth_service/count_failures.py",
        "src/auth_service/test_count_failures.py",
    }
    code = found["src/auth_service/count_failures.py"]
    assert (code.kind, code.units, code.requirements) == (
        "code",
        {"count-failures": 1},
        {"REQ-0047": 1},
    )
    assert found["src/auth_service/test_count_failures.py"].kind == "test"


def test_a_test_names_its_variables_and_security_templates(tmp_path):
    from product_builder import SECURITY_TEST, write_security_test

    from tools.run_stack_commands_tool import read_stack

    root = build_python_product(tmp_path)
    write_security_test(root)
    config = read_product_config(root)
    (test,) = scan_sources(config, read_stack(config))
    assert test.path == SECURITY_TEST
    assert (test.units, test.security, test.env) == (
        {"signin-form": 1},
        {"input-validation": 1},
        {},
    )


def test_integration_tests_name_their_component_flow_and_requirement(tmp_path):
    from product_builder import FLOW_TEST, write_all_integration_tests

    from tools.read_unit_markers_tool import scan_integration_tests
    from tools.run_stack_commands_tool import read_stack

    root = build_python_product(tmp_path)
    write_all_integration_tests(root)
    (root / "it" / "notes.md").write_text("@flow[ignored]")
    config = read_product_config(root)
    found = {s.path: s for s in scan_integration_tests(config, read_stack(config))}
    assert set(found) == {
        "it/test_web_app_component.py",
        "it/test_auth_service_component.py",
        FLOW_TEST,
    }
    assert found["it/test_web_app_component.py"].components == {"web-app": 1}
    flow = found[FLOW_TEST]
    assert (flow.kind, flow.flows, flow.requirements) == (
        "integration",
        {"login": 1},
        {"REQ-0048": 1},
    )
    assert not any(s.path.startswith("it/") for s in scan_sources(config, read_stack(config)))


def test_software_tests_name_their_requirements(tmp_path):
    from product_builder import E2E_TEST, SOFTWARE_TEST, write_all_software_tests

    from tools.read_unit_markers_tool import scan_software_tests
    from tools.run_stack_commands_tool import read_stack

    root = build_python_product(tmp_path)
    write_all_software_tests(root)
    (root / "st" / "notes.md").write_text("@sdoc[REQ-0001]")
    config = read_product_config(root)
    found = {s.path: s for s in scan_software_tests(config, read_stack(config))}
    assert set(found) == {E2E_TEST, SOFTWARE_TEST, "st/bench/test_lockout_bench.py"}
    assert found[E2E_TEST].kind == "software"
    assert set(found[SOFTWARE_TEST].requirements) == {"REQ-0049", "REQ-0050", "REQ-0053"}
