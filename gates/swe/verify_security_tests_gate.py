"""verify_security_tests_gate — principle #16: every trust boundary has its security tests.

A component crosses a trust boundary when it is the product's end of an
interface marked external: true (decision 24); that interface names the
security test templates the boundary needs, from the framework's catalog
(decisions 25 and 26). For each such component and template, at least one unit
test of the component — a test file with an @unit marker of one of its units —
names the template as @security[<template>] and has a passing result in the unit
suite (decisions 27 and 28). Every @security marker names a catalog template.
Whether the tests really show what the template asks is the reviewer's.
On a selected run only the components it covers need their security tests
(decision 32).

    python gates/swe/verify_security_tests_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_test_results_tool import ResultsError, map_to_file, read_results  # noqa: E402
from tools.read_unit_markers_tool import design_units, scan_sources  # noqa: E402
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import CommandRun, read_stack, run_command  # noqa: E402
from tools.validate_contract_tool import contract_path, validate  # noqa: E402

GATE = "verify_security_tests_gate"


def catalog() -> list[str]:
    """The framework's security test templates, as interface.v1 lists them."""
    schema = json.loads(contract_path("interface").read_text(encoding="utf-8"))
    return schema["properties"]["security_templates"]["items"]["enum"]


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    if stack is None:
        return []  # check_stack_decision_gate reports a missing or broken stack
    known = set(catalog())
    findings: list[Finding] = []
    tests = {s.path: s for s in scan_sources(config, stack) if s.kind == "test"}
    for source in tests.values():
        for template, line in source.security.items():
            if template not in known:
                findings.append(
                    Finding(
                        "UNKNOWN_TEMPLATE",
                        source.path,
                        line,
                        f"@security[{template}] names no template of the catalog: "
                        f"{', '.join(sorted(known))}.",
                    )
                )
    required = _boundaries(config)
    if not required:
        return findings
    covered, run = _covered(config, stack, tests)
    for (component, template), (path, line, interface) in sorted(required.items()):
        if not run.covers("components", component):
            continue  # a selected run that does not cover this component
        if template not in covered.get(component, set()):
            findings.append(
                Finding(
                    "MISSING_SECURITY_TEST",
                    path,
                    line,
                    f"Interface {interface} crosses into {component}, which has no passing "
                    f"unit test marked @security[{template}].",
                )
            )
    return findings


def _boundaries(config: ProductConfig) -> dict[tuple[str, str], tuple[str, int | None, str]]:
    """(component, template) → where the external interface asks for it. Only
    valid blocks count; their form is check_design_contract_gate's to report."""
    folder = config.architecture_dir
    files = sorted(folder.glob("*.md")) if folder.is_dir() else []
    roles: dict[str, str] = {}
    interfaces = []
    for path in files:
        for block in read_yaml_blocks(path, "component"):
            if isinstance(block.data, dict) and not validate(block.data, "component"):
                roles.setdefault(block.data["id"], block.data["role"])
        for block in read_yaml_blocks(path, "interface"):
            if isinstance(block.data, dict) and not validate(block.data, "interface"):
                interfaces.append((config.relative(path), block))
    required: dict[tuple[str, str], tuple[str, int | None, str]] = {}
    for shown, block in interfaces:
        data = block.data
        if not data["external"]:
            continue
        line = block.key_lines.get("security_templates", block.line)
        for end in (data["from"], data["to"]):
            if roles.get(end) != "component":
                continue
            for template in data["security_templates"]:
                required.setdefault((end, template), (shown, line, data["id"]))
    return required


def _covered(
    config: ProductConfig, stack: dict, tests: dict
) -> tuple[dict[str, set[str]], CommandRun]:
    """component → the templates named by its test files with a passing result,
    and the unit-suite run they come from."""
    run = run_command(config, "suites", "unit", stack["suites"]["unit"])
    try:
        results = read_results(run.result_paths)
    except ResultsError:
        return {}, run
    passing = {
        file
        for result in results
        if result.outcome == "passed" and (file := map_to_file(result, list(tests))) is not None
    }
    owner = {unit: component for unit, (component, _design) in design_units(config).items()}
    covered: dict[str, set[str]] = {}
    for file in passing:
        source = tests[file]
        for unit in source.units:
            if unit in owner:
                covered.setdefault(owner[unit], set()).update(source.security)
    return covered, run


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
