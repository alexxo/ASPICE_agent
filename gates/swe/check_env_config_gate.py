"""check_env_config_gate — principle #23: environment variables declared, read and validated.

The code files are searched with the stack's env_read_patterns (decision 19);
every variable they read is declared in qf.yaml paths.env_variables_file, and
every declared variable is read somewhere (decision 22). Every required
variable is named with @env[<NAME>] by at least one unit test that passes in the
unit suite's results (decision 21): the test shows the software stops at
start-up when the variable is missing or invalid. A read whose name is computed
at run time matches no pattern; the reviewer checks it.
Every required variable having its test is judged on full runs only (decision
32).

    python gates/swe/check_env_config_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_test_results_tool import ResultsError, map_to_file, read_results  # noqa: E402
from tools.read_unit_markers_tool import scan_sources  # noqa: E402
from tools.read_yaml_blocks_tool import read_yaml_blocks  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack, run_command  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

GATE = "check_env_config_gate"


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    if stack is None:
        return []  # check_stack_decision_gate reports a missing or broken stack
    patterns, findings = _patterns(config, stack)
    declared = _declared(config)
    sources = scan_sources(config, stack)
    reads: dict[str, tuple[str, int]] = {}
    for source in sources:
        if source.kind != "code":
            continue
        for number, line in enumerate(source.text.splitlines(), start=1):
            for pattern in patterns:
                for name in pattern.findall(line):
                    reads.setdefault(name, (source.path, number))
    shown = config.relative(config.env_variables_file)
    for name, (path, line) in sorted(reads.items()):
        if name not in declared:
            findings.append(
                Finding(
                    "UNDECLARED_VARIABLE",
                    path,
                    line,
                    f"{name} is read here but not declared in {shown}; declare it with the "
                    "detailed design.",
                )
            )
    for name in sorted(set(declared) - set(reads)):
        findings.append(
            Finding("UNUSED_VARIABLE", shown, None, f"{name} is declared but no code reads it.")
        )
    tests = {s.path: s for s in sources if s.kind == "test"}
    for source in tests.values():
        for name, line in source.env.items():
            if name not in declared:
                findings.append(
                    Finding(
                        "UNKNOWN_VARIABLE",
                        source.path,
                        line,
                        f"@env[{name}] names no declared variable.",
                    )
                )
    required = sorted(name for name, needed in declared.items() if needed)
    if required:
        validated = _validated(config, stack, tests)
        for name in required if validated is not None else []:
            if name not in validated:
                findings.append(
                    Finding(
                        "UNTESTED_VARIABLE",
                        shown,
                        None,
                        f"{name} is required, but no passing unit test names it with "
                        f"@env[{name}] to show the software stops without it.",
                    )
                )
    return findings


def _patterns(config: ProductConfig, stack: dict) -> tuple[list[re.Pattern], list[Finding]]:
    shown = config.relative(config.stack_file)
    patterns, findings = [], []
    for text in stack["env_read_patterns"]:
        try:
            pattern = re.compile(text)
        except re.error as err:
            findings.append(
                Finding("INVALID_READ_PATTERN", shown, None, f"'{text}' is no regex: {err}.")
            )
            continue
        if pattern.groups != 1:
            findings.append(
                Finding(
                    "INVALID_READ_PATTERN",
                    shown,
                    None,
                    f"'{text}' has {pattern.groups} groups; it needs one, for the name.",
                )
            )
            continue
        patterns.append(pattern)
    return patterns, findings


def _declared(config: ProductConfig) -> dict[str, bool]:
    """Every readable, valid declaration: name → required. Their form is
    check_detailed_design_contract_gate's to report."""
    path = config.env_variables_file
    declared: dict[str, bool] = {}
    for block in read_yaml_blocks(path, "env_variable") if path.is_file() else []:
        if isinstance(block.data, dict) and not validate(block.data, "env_variable"):
            declared.setdefault(block.data["name"], block.data["required"])
    return declared


def _validated(config: ProductConfig, stack: dict, tests: dict) -> set[str] | None:
    """The variables named by a test file with at least one passing result; None
    on a selected run, which leaves the check to the full run (decision 32)."""
    run = run_command(config, "suites", "unit", stack["suites"]["unit"])
    if not run.full:
        return None
    try:
        results = read_results(run.result_paths)
    except ResultsError:
        return set()
    names: set[str] = set()
    for result in results:
        file = map_to_file(result, list(tests))
        if file is not None and result.outcome == "passed":
            names.update(tests[file].env)
    return names


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
