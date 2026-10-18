"""Select the tests traced to a change, for the coder's own loop (decisions 30–33
of the unit stages).

CI runs every test on every change (decision 32); this selection is what the
coder runs while working, and what a gate run with QF_RUN=selected runs
(run_stack_commands_tool). The change is every file of the
commits since the base (read_commit_range_tool: --base, QF_BASE, else the merge
base with the main branch) and every uncommitted file. Each changed file is
traced through its markers:

- code names its units (@unit) and may name requirements (@sdoc);
- a unit test, a component or integration test and a software-level test is
  selected itself, and what it names joins the scope.

The scope grows along the architecture: a unit's component (the detailed
design), the components joined to it by an interface, the requirements those
components meet, and the approved sequence diagrams any of them takes part in.
The unit suite then runs the unit tests naming a unit in scope; the integration
suite the tests naming a component, flow or requirement in scope; the software
suite the tests naming a requirement in scope. Every selected test keeps its
reasons — the changed file and the marker that links them — for the
verification report (decision 30).

Every test runs instead (a full run) when a release is proposed, when there is
no base or nothing changed, when a changed file traces to nothing (no marker,
deleted, or no code or test at all), and for a suite without run_selected or
outside the unit, integration and software levels.

    python tools/select_tests_tool.py [--root PRODUCT] [--base REF]
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.read_commit_range_tool import commits, resolve_base, uncommitted  # noqa: E402
from tools.read_product_config_tool import (  # noqa: E402
    ConfigError,
    ProductConfig,
    read_product_config,
)
from tools.read_unit_markers_tool import (  # noqa: E402
    SourceFile,
    design_units,
    scan_integration_tests,
    scan_software_tests,
    scan_sources,
)

__all__ = ["LEVELS", "Scope", "Selection", "Trace", "select", "selected_tests_argument", "trace"]

# suite → its section of the verification plan; other suites always run in full
LEVELS = {"unit": "unit", "integration": "integration", "software": "software"}


@dataclass(frozen=True)
class Scope:
    """What a selected run covers: the gates check completeness only for these."""

    units: frozenset[str] = frozenset()
    components: frozenset[str] = frozenset()
    flows: frozenset[str] = frozenset()
    requirements: frozenset[str] = frozenset()

    def as_dict(self) -> dict[str, list[str]]:
        kinds = ("units", "components", "flows", "requirements")
        return {k: sorted(getattr(self, k)) for k in kinds}


@dataclass(frozen=True)
class Trace:
    """The change traced through the markers; full is the reason it could not be."""

    full: str | None
    scope: Scope = field(default_factory=Scope)
    changed: dict[str, list[str]] = field(default_factory=dict)  # test file → its reasons


@dataclass(frozen=True)
class Selection:
    suite: str
    full: str | None  # why every test runs; None for a selected run
    tests: dict[str, list[str]] = field(default_factory=dict)  # test file → its reasons
    scope: Scope | None = None  # None for a full run

    @property
    def selected(self) -> bool:
        return self.full is None


def _proposed_release(config: ProductConfig) -> bool:
    from tools.write_release_tool import pending

    return bool(pending(config))


def _changed(config: ProductConfig) -> tuple[list[str] | None, str | None]:
    """The changed files, or why the change cannot be read."""
    root = config.root
    base = resolve_base(root)
    if base is None:
        return None, "there is no base to compare with"
    paths = {c.path for commit in commits(root, base) for c in commit.changes}
    paths |= set(uncommitted(root))
    if not paths:
        return None, "nothing changed since the base"
    return sorted(paths), None


def trace(config: ProductConfig, stack: dict) -> Trace:
    """The change traced through the markers, shared by every suite."""
    if _proposed_release(config):
        return Trace("a release is proposed: the release commit runs every test")
    changed, why = _changed(config)
    if changed is None:
        return Trace(why)

    sources = scan_sources(config, stack)
    integration = scan_integration_tests(config, stack)
    software = scan_software_tests(config, stack)
    known: dict[str, SourceFile] = {s.path: s for s in [*sources, *integration, *software]}
    owner = {unit: component for unit, (component, _design) in design_units(config).items()}

    units: set[str] = set()
    components: set[str] = set()
    requirements: set[str] = set()
    named_flows: set[str] = set()
    tests: dict[str, list[str]] = {}
    for path in changed:
        source = known.get(path)
        if source is None or not (config.root / path).is_file():
            return Trace(f"{path} changed and traces to no unit, component or requirement")
        names = [*source.units, *source.components, *source.flows, *source.requirements]
        if not names:
            return Trace(f"{path} changed and names no unit, component, flow or requirement")
        units.update(source.units)
        components.update(source.components)
        requirements.update(source.requirements)
        named_flows.update(source.flows)
        if source.kind != "code":
            tests.setdefault(path, []).append(f"{path} changed")

    from tools.read_integration_tool import read_architecture, read_flows

    architecture = read_architecture(config)
    components |= {owner[u] for u in units if u in owner}
    for interface in architecture.interfaces:
        if interface["from"] in components or interface["to"] in components:
            components |= {interface["from"], interface["to"]}
    for component in components:
        requirements.update(architecture.meets.get(component, ()))
    flows = named_flows | {
        flow
        for flow, (_file, pairs) in read_flows(config).items()
        if components & {p for pair in pairs for p in pair}
    }
    scope = Scope(*(frozenset(s) for s in (units, components, flows, requirements)))
    return Trace(None, scope, tests)


def select(
    config: ProductConfig, stack: dict, suite: str, traced: Trace | None = None
) -> Selection:
    """Which tests of one suite run, and why."""
    entry = stack["suites"].get(suite, {})
    if suite not in LEVELS:
        return Selection(suite, f"the {suite} suite always runs in full")
    if "run_selected" not in entry:
        return Selection(suite, f"suites.{suite} declares no run_selected")
    traced = traced if traced is not None else trace(config, stack)
    if traced.full is not None:
        return Selection(suite, traced.full)
    scope = traced.scope
    candidates = {
        "unit": [s for s in scan_sources(config, stack) if s.kind == "test"],
        "integration": scan_integration_tests(config, stack),
        "software": scan_software_tests(config, stack),
    }[suite]
    tests: dict[str, list[str]] = {}
    for test in candidates:
        reasons = list(traced.changed.get(test.path, []))
        reasons += [f"@unit[{u}] is in the change" for u in test.units if u in scope.units]
        if suite == "integration":
            named = [c for c in test.components if c in scope.components]
            reasons += [f"@component[{c}] is in the change" for c in named]
            reasons += [f"@flow[{f}] is in the change" for f in test.flows if f in scope.flows]
        if suite in ("integration", "software"):
            reasons += [
                f"@sdoc[{r}] is in the change" for r in test.requirements if r in scope.requirements
            ]
        if reasons:
            tests[test.path] = reasons
    return Selection(suite, None, tests, scope)


def selected_tests_argument(selection: Selection, entry: dict) -> str:
    """What replaces {tests} in run_selected."""
    if entry["selected_form"] == "names":
        return ",".join(PurePosixPath(p).stem for p in sorted(selection.tests))
    return " ".join(shlex.quote(p) for p in sorted(selection.tests))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base", help="the ref the change starts after (default: QF_BASE)")
    args = parser.parse_args(argv)
    try:
        config = read_product_config(args.root)
    except ConfigError as err:
        print(err.message, file=sys.stderr)
        return 2
    if args.base:
        os.environ["QF_BASE"] = args.base
    from tools.run_stack_commands_tool import read_stack

    stack = read_stack(config)
    if stack is None:
        print("The stack is missing or invalid: nothing to select.", file=sys.stderr)
        return 2
    traced = trace(config, stack)
    out = {}
    for suite in stack["suites"]:
        s = select(config, stack, suite, traced)
        out[suite] = {"full": s.full, "tests": s.tests}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
