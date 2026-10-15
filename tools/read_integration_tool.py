"""What the stage 7 and 8 gates share: the architecture's components and
interfaces, the approved flows, the plan's integration steps, and one run of a
suite tied to its test files.

Only valid blocks and faithfully readable diagrams count; their form is the
design and diagram gates' to report. Every suite runs once per tree (decision
13 of the unit stages); a test file passes when at least one of its results
passed — a failing one is reported by the gate that judges its level.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from adapters.read_archify_diagram_adapter import read_archify_diagrams
from tools.read_product_config_tool import ProductConfig
from tools.read_test_results_tool import ResultsError, TestResult, map_to_file, read_results
from tools.read_unit_markers_tool import SourceFile
from tools.read_yaml_blocks_tool import read_yaml_blocks
from tools.run_stack_commands_tool import CommandRun, run_command
from tools.validate_contract_tool import validate

__all__ = [
    "Architecture",
    "SuiteRun",
    "integration_steps",
    "read_architecture",
    "read_flows",
    "run_integration",
    "run_suite",
]


@dataclass(frozen=True)
class Architecture:
    roles: dict[str, str] = field(default_factory=dict)  # component ID → role
    meets: dict[str, list[str]] = field(default_factory=dict)  # component ID → its REQ-UIDs
    places: dict[str, tuple[str, int]] = field(default_factory=dict)  # ID → (file, line)
    interfaces: list[dict] = field(default_factory=list)  # each with its file and line

    @property
    def components(self) -> list[str]:
        """The components of role component — the ones the product builds."""
        return sorted(c for c, role in self.roles.items() if role == "component")

    def internal_interfaces(self) -> list[dict]:
        built = set(self.components)
        return [i for i in self.interfaces if i["from"] in built and i["to"] in built]


def read_architecture(config: ProductConfig) -> Architecture:
    folder = config.architecture_dir
    arch = Architecture()
    for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        shown = config.relative(path)
        for block in read_yaml_blocks(path, "component"):
            if isinstance(block.data, dict) and not validate(block.data, "component"):
                arch.roles.setdefault(block.data["id"], block.data["role"])
                arch.meets.setdefault(block.data["id"], list(block.data.get("meets", [])))
                arch.places.setdefault(block.data["id"], (shown, block.line))
        for block in read_yaml_blocks(path, "interface"):
            if isinstance(block.data, dict) and not validate(block.data, "interface"):
                arch.interfaces.append({**block.data, "file": shown, "line": block.line})
    return arch


def read_flows(config: ProductConfig) -> dict[str, tuple[str, set[frozenset[str]]]]:
    """Every approved sequence diagram: ID → (its file, the pairs of participants
    its messages join)."""
    flows: dict[str, tuple[str, set[frozenset[str]]]] = {}
    for _path, result in read_archify_diagrams(config.diagrams_dir, config.root):
        diagram = result.diagram
        if diagram is None or result.problems or diagram["type"] != "sequence":
            continue
        pairs = {
            frozenset((e["from"], e["to"])) for e in diagram["elements"] if e["kind"] == "message"
        }
        flows[diagram["diagram"]] = (diagram["source"], pairs)
    return flows


@dataclass(frozen=True)
class SuiteRun:
    results: list[TestResult] | None  # None when the suite wrote no readable results
    by_file: dict[str, list[TestResult]]  # test file → its results
    measurements: list[str] = field(default_factory=list)  # measurements files kept
    run: CommandRun | None = None  # None when nothing ran

    def covers(self, kind: str, ident: str) -> bool:
        """Whether this run had to cover the unit, component, flow or requirement
        (decision 32 of the unit stages): always, unless it ran a selection."""
        return self.run is None or self.run.covers(kind, ident)

    @property
    def passing(self) -> set[str]:
        return {f for f, rs in self.by_file.items() if any(r.outcome == "passed" for r in rs)}


def run_suite(config: ProductConfig, stack: dict, name: str, tests: list[SourceFile]) -> SuiteRun:
    """Run one suite once per tree and tie its results to the given test files;
    a suite the stack does not declare has no results."""
    if name not in stack["suites"]:
        return SuiteRun(None, {})
    run = run_command(config, "suites", name, stack["suites"][name])
    try:
        results = read_results(run.result_paths) if run.results else None
    except ResultsError:
        results = None
    if results is None and run.ran_nothing:
        results = []  # no test was traced to the change, so none ran
    by_file: dict[str, list[TestResult]] = {}
    files = [t.path for t in tests]
    for result in results or []:
        file = map_to_file(result, files)
        if file is not None:
            by_file.setdefault(file, []).append(result)
    return SuiteRun(results, by_file, list(run.measurements), run)


def run_integration(config: ProductConfig, stack: dict, tests: list[SourceFile]) -> SuiteRun:
    """Run the integration suite once; nothing to run means no results."""
    if not tests:
        return SuiteRun([], {})
    return run_suite(config, stack, "integration", tests)


def integration_steps(config: ProductConfig) -> list[tuple[dict, int | None]]:
    """The steps of a valid plan's integration order, each with the order's
    line; the plan's form is check_verification_plan_gate's to report."""
    path = config.verification_plan_file
    blocks = read_yaml_blocks(path, "verification_plan") if path.is_file() else []
    if len(blocks) != 1 or not isinstance(blocks[0].data, dict):
        return []
    plan = blocks[0].data
    if validate(plan, "verification_plan") or "integration" not in plan:
        return []
    line = blocks[0].key_lines.get("order", blocks[0].line)
    return [(step, line) for step in plan["integration"]["order"]]
