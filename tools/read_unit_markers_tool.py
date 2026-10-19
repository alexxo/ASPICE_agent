"""Find the unit and requirement markers in a product's code and tests.

Under qf.yaml paths.code_dir, a file matching the plan's unit suite test_files
is a test and one matching the stack's code_files (and not test_files) is code
(decision 14). Each
names the unit it implements or verifies as @unit[<unit-id>], and code may name
the requirement it implements as @sdoc[<REQ-UID>]; a test names the environment
variable it validates as @env[<NAME>] (decision 21), and the security test
template it applies as @security[<template>] (decision 28). The units are the
```yaml unit blocks of the detailed design, one <component-id>.md per component.

Under paths.integration_tests_dir, a file matching the integration suite's
test_files is a component or integration test (stage 7, decision
2): it names its component as @component[<id>] or its flow as @flow[<id>], and
the observability requirement whose events it asserts as @sdoc[<REQ-UID>].

Under paths.software_tests_dir, a file matching the software suite's test_files
is a software-level test (stage 8, decision 2 of the software verification
stage): it names the requirement it verifies as @sdoc[<REQ-UID>].
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from tools.read_product_config_tool import ProductConfig
from tools.read_yaml_blocks_tool import read_yaml_blocks

__all__ = [
    "SourceFile",
    "classify",
    "design_units",
    "glob_match",
    "in_component_folder",
    "markers",
    "problem_markers",
    "scan_integration_tests",
    "scan_software_tests",
    "scan_sources",
]

UNIT = re.compile(r"@unit\[([^\]\s]+)\]")
SDOC = re.compile(r"@sdoc\[([^\]\s]+)\]")
ENV = re.compile(r"@env\[([^\]\s]+)\]")
SECURITY = re.compile(r"@security\[([^\]\s]+)\]")
COMPONENT = re.compile(r"@component\[([^\]\s]+)\]")
FLOW = re.compile(r"@flow\[([^\]\s]+)\]")
PROBLEM = re.compile(r"@problem\[([0-9]+)\]")


@dataclass(frozen=True)
class SourceFile:
    path: str  # repository-relative, posix
    kind: str  # "code", "test", "integration" or "software"
    units: dict[str, int] = field(default_factory=dict)  # unit ID → first line naming it
    requirements: dict[str, int] = field(default_factory=dict)  # REQ-UID → first line
    env: dict[str, int] = field(default_factory=dict)  # variable → first line
    security: dict[str, int] = field(default_factory=dict)  # template → first line
    components: dict[str, int] = field(default_factory=dict)  # component → first line
    flows: dict[str, int] = field(default_factory=dict)  # sequence diagram → first line
    text: str = field(default="", repr=False, compare=False)


def _glob_regex(pattern: str) -> re.Pattern:
    parts = pattern.split("/")
    out = ""
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if part == "**":
            out += ".*" if last else "(?:.*/)?"
            continue
        seg = "".join("[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c) for c in part)
        out += seg if last else seg + "/"
    return re.compile(f"^{out}$")


def glob_match(path: str, patterns: list[str]) -> bool:
    """Whether a posix path matches any glob; ** spans any number of folders."""
    return any(_glob_regex(p).match(path) for p in patterns)


def classify(path_in_code_dir: str, stack: dict) -> str | None:
    """'test', 'code', or None for a file that is neither."""
    if glob_match(path_in_code_dir, stack.get("test_files", [])):
        return "test"
    if glob_match(path_in_code_dir, stack.get("code_files", [])):
        return "code"
    return None


def markers(text: str) -> tuple[dict[str, int], dict[str, int]]:
    """The unit IDs and requirement UIDs a text names, each with its first line."""
    units: dict[str, int] = {}
    reqs: dict[str, int] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        for found in UNIT.findall(line):
            units.setdefault(found, number)
        for found in SDOC.findall(line):
            reqs.setdefault(found, number)
    return units, reqs


def _first_lines(pattern: re.Pattern, text: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        for name in pattern.findall(line):
            found.setdefault(name, number)
    return found


def scan_sources(config: ProductConfig, stack: dict) -> list[SourceFile]:
    """Every code and test file under paths.code_dir, with its markers."""
    base = config.code_dir
    if not base.is_dir():
        return []
    found = []
    for path in sorted(base.rglob("*")):
        inner = path.relative_to(base)
        if not path.is_file() or any(p.startswith(".") for p in inner.parts):
            continue
        kind = classify(inner.as_posix(), stack)
        if kind is None:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        units, reqs = markers(text)
        env = _first_lines(ENV, text)
        security = _first_lines(SECURITY, text)
        found.append(SourceFile(config.relative(path), kind, units, reqs, env, security, text=text))
    return found


def _scan_folder(base: Path, patterns: list[str]) -> list[tuple[Path, str]]:
    """Every file under base matching a pattern, with its text; hidden folders
    and files that are not UTF-8 text are left out."""
    if not base.is_dir():
        return []
    found = []
    for path in sorted(base.rglob("*")):
        inner = path.relative_to(base)
        if not path.is_file() or any(p.startswith(".") for p in inner.parts):
            continue
        if not glob_match(inner.as_posix(), patterns):
            continue
        try:
            found.append((path, path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
    return found


def scan_integration_tests(config: ProductConfig, stack: dict) -> list[SourceFile]:
    """Every component and integration test under paths.integration_tests_dir."""
    found = []
    for path, text in _scan_folder(
        config.integration_tests_dir, stack.get("integration_test_files", [])
    ):
        units, reqs = markers(text)
        found.append(
            SourceFile(
                config.relative(path),
                "integration",
                units,
                reqs,
                components=_first_lines(COMPONENT, text),
                flows=_first_lines(FLOW, text),
                text=text,
            )
        )
    return found


def scan_software_tests(config: ProductConfig, stack: dict) -> list[SourceFile]:
    """Every software-level test under paths.software_tests_dir."""
    found = []
    for path, text in _scan_folder(config.software_tests_dir, stack.get("software_test_files", [])):
        units, reqs = markers(text)
        found.append(SourceFile(config.relative(path), "software", units, reqs, text=text))
    return found


def design_units(config: ProductConfig) -> dict[str, tuple[str, str]]:
    """Every unit of the detailed design: ID → (component ID, design file)."""
    folder = config.detailed_design_dir
    units: dict[str, tuple[str, str]] = {}
    for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        for block in read_yaml_blocks(path, "unit"):
            data = block.data if isinstance(block.data, dict) else {}
            uid = data.get("id")
            if isinstance(uid, str):
                units.setdefault(uid, (path.stem, config.relative(path)))
    return units


def in_component_folder(path: str, component: str) -> bool:
    """Whether a folder of the path is named after the component (- may be _)."""
    names = {component, component.replace("-", "_")}
    return any(part in names for part in Path(path).parent.parts)


def problem_markers(config: ProductConfig, stack: dict) -> dict[int, list[tuple[str, int]]]:
    """Every problem a test names with @problem[<n>], with each (test file, line)
    naming it; tests of every level count, code does not."""
    tests = [s for s in scan_sources(config, stack) if s.kind == "test"]
    tests += scan_integration_tests(config, stack) + scan_software_tests(config, stack)
    found: dict[int, list[tuple[str, int]]] = {}
    for test in tests:
        for name, line in _first_lines(PROBLEM, test.text).items():
            found.setdefault(int(name), []).append((test.path, line))
    return found
