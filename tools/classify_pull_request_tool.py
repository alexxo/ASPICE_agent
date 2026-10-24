"""Classify a pull request: does a person review it, and on what (rule 14 of the
quality assurance stage).

A person reviews a pull request that is important, risky, or both — never one
chosen by number. Importance is the architect's own rating at checkpoint 2,
reached through the links the files already carry:

- code and tests name their requirements (@sdoc), else their unit (@unit, whose
  component meets requirements) or component (@component); a detailed design
  is its component's; every changed file of the change contributes;
- important: a requirement of criticality high or of kind security, or a trust
  boundary — an interface of a component in the change that is external or has
  security templates, or a test with a security template (@security);
- a changed file that is neither documentation, nor an approved input of an
  earlier checkpoint, nor a marked source or test (a build, dependency or
  configuration file) traces to nothing, so it counts as touching every
  requirement and every interface.

Risky, from the change itself and the reviewer agent's review record
(review.v1): the evidence got weaker — a test file deleted, fewer tests in a
file, a test switched off (skip, xfail, disabled), or the verification plan's
coverage minimum lowered or a time budget loosened, against the base; a
finding withdrawn or disputed without a change; the reviewer agent asks for a
person, for one of five conditions. A pull request that changes the
architecture or the gates' own files is always reviewed. Nothing else is.

The classification also says what the person reviews: the detailed designs
changed, the tests to describe (those linked to what made the pull request
important, else every changed test), the weakenings, the disputes and the
reviewer agent's request.

    python tools/classify_pull_request_tool.py --root PRODUCT --pull-request N \\
        [--record review.yaml] [--base REF]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.read_commit_range_tool import file_at, resolve_base  # noqa: E402
from tools.read_product_config_tool import (  # noqa: E402
    ConfigError,
    ProductConfig,
    read_product_config,
)
from tools.read_yaml_blocks_tool import yaml_blocks_in_text  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

__all__ = ["Classification", "Weakening", "classify", "review_record"]

# A test switched off, in the languages the framework meets.
SWITCHED_OFF = re.compile(
    r"@(?:pytest\.mark\.)?(?:skip|skipif|xfail)\b|pytest\.(?:skip|xfail)\(|@Disabled\b|@Ignore\b"
    r"|\b(?:it|test|describe)\.(?:skip|todo)\(|\bx(?:it|describe|test)\(|\bt\.Skip\("
)
# A test declared, to count tests in a file.
DECLARED = re.compile(
    r"^\s*(?:async\s+)?def\s+test|@Test\b|@ParameterizedTest\b|^\s*(?:it|test)\s*\(|^\s*func\s+Test"
)


@dataclass(frozen=True)
class Weakening:
    file: str
    before: str
    now: str


@dataclass(frozen=True)
class Classification:
    reasons: tuple[str, ...] = ()  # why a person reviews it, in plain words; empty: no one
    designs: tuple[str, ...] = ()  # components whose detailed design changed
    tests: tuple[str, ...] = ()  # changed test files the person reviews
    requirements: dict[str, list[str]] = field(default_factory=dict)  # test file → its REQ-UIDs
    weakenings: tuple[Weakening, ...] = ()
    disputes: tuple[dict, ...] = ()
    request: dict | None = None  # the reviewer agent's own request

    @property
    def needed(self) -> bool:
        return bool(self.reasons)

    def as_dict(self) -> dict:
        return {
            "needed": self.needed,
            "reasons": list(self.reasons),
            "designs": list(self.designs),
            "tests": list(self.tests),
            "requirements": self.requirements,
            "weakenings": [w.__dict__ for w in self.weakenings],
            "disputes": list(self.disputes),
            "request": self.request,
        }


def review_record(body: str) -> tuple[dict | None, str | None]:
    """The review's one ```yaml review block, checked against review.v1, or None
    and why it does not count."""
    blocks = yaml_blocks_in_text(body, "review", Path("review"))
    if len(blocks) != 1:
        return None, f"it holds {len(blocks)} ```yaml review blocks, not one"
    if blocks[0].error:
        return None, f"its review block cannot be read: {blocks[0].error}"
    violations = validate(blocks[0].data, "review")
    if violations:
        first = violations[0]
        return None, f"its review block breaks review.v1 at '{first.path or 'the block'}': " + (
            first.message
        )
    return blocks[0].data, None


def always(config: ProductConfig, files) -> str | None:
    """Why every pull request like this one is reviewed by a person, or None."""
    architecture = config.relative(config.architecture_dir).rstrip("/") + "/"
    if any(f.startswith(architecture) for f in files):
        return f"changes the architecture ({architecture})"
    pin = config.relative(config.framework_dir).rstrip("/")
    guarded = {config.relative(config.ci_file), pin, ".gitmodules", "qf.yaml"}
    touched = sorted(guarded & set(files))
    if touched:
        return f"changes the gates' own files ({', '.join(touched)})"
    return None


def classify(
    config: ProductConfig, files, record: dict | None = None, base: str | None = None
) -> Classification:
    """Whether a person reviews the change of these files, why, and on what."""
    files = sorted(set(files))
    reasons: list[str] = []
    first = always(config, files)
    if first:
        reasons.append(first)
    traced = _trace(config, files)
    reasons += traced.reasons
    weakenings = _weakenings(config, files, traced.stack, base) if base else []
    for w in weakenings:
        reasons.append(f"weakens a test: {w.file} ({w.now})")
    record = record or {}
    disputes = tuple(f for f in record.get("findings", []) if f["outcome"] != "fixed")
    if disputes:
        reasons.append(f"{len(disputes)} reviewer finding(s) closed without a change")
    request = record.get("person") if isinstance(record.get("person"), dict) else None
    if request:
        reasons.append(f"the reviewer agent asks for a person: {request['reason']}")
    tests = traced.important_tests if traced.important_tests else traced.tests
    return Classification(
        tuple(reasons),
        tuple(traced.designs),
        tuple(tests) if reasons else (),
        {t: traced.links.get(t, []) for t in tests} if reasons else {},
        tuple(weakenings),
        disputes,
        request,
    )


@dataclass
class _Traced:
    reasons: list[str] = field(default_factory=list)
    designs: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    important_tests: list[str] = field(default_factory=list)
    links: dict[str, list[str]] = field(default_factory=dict)
    stack: dict | None = None


def _documentation(config: ProductConfig) -> list[str]:
    """Folders and files reviewed elsewhere: approved at an earlier checkpoint, or
    documentation with no effect on the product's behaviour."""
    paths = (
        config.diagrams_dir,
        config.requirements_dir,
        config.approvals_dir,
        config.wishes_file,
        config.glossary_file,
        config.stack_file,
        config.decisions_dir,
        config.framework_feedback_file,
        config.releases_dir,
        config.verification_plan_file,  # its loosening is a weakening
    )
    return [config.relative(p) for p in paths]


def _under(path: str, roots: list[str]) -> bool:
    return any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)


def _trace(config: ProductConfig, files: list[str]) -> _Traced:
    from tools.read_integration_tool import read_architecture
    from tools.read_requirements_tool import read_requirements
    from tools.read_unit_markers_tool import (
        design_units,
        scan_integration_tests,
        scan_software_tests,
        scan_sources,
    )
    from tools.run_stack_commands_tool import read_stack

    out = _Traced()
    stack = read_stack(config)
    out.stack = stack
    known = {}
    if stack is not None:
        for s in [
            *scan_sources(config, stack),
            *scan_integration_tests(config, stack),
            *scan_software_tests(config, stack),
        ]:
            known[s.path] = s
    owner = {unit: component for unit, (component, _design) in design_units(config).items()}
    architecture = read_architecture(config)
    ratings = {
        r.data["uid"]: r.data
        for r in read_requirements(config)
        if isinstance(r.data.get("uid"), str)
    }
    documentation = _documentation(config)
    design_dir = config.relative(config.detailed_design_dir).rstrip("/") + "/"
    architecture_dir = config.relative(config.architecture_dir).rstrip("/") + "/"

    everything: list[str] = []
    per_file: dict[str, tuple[set[str], set[str], bool]] = {}  # file → reqs, components, security
    for path in files:
        if path.startswith(architecture_dir) or always(config, [path]):
            continue  # reviewed for its own reason
        if path.startswith(design_dir):
            component = PurePosixPath(path).name.split(".")[0]
            if component not in out.designs:
                out.designs.append(component)
            per_file[path] = (set(architecture.meets.get(component, ())), {component}, False)
            continue
        source = known.get(path)
        if source is None:
            if path.endswith(".md") or _under(path, documentation):
                continue
            if not (config.root / path).is_file():
                continue  # deleted: a deleted test is a weakening, other code needs nothing
            everything.append(path)
            continue
        components = set(source.components) | {owner[u] for u in source.units if u in owner}
        if source.requirements:
            reqs = set(source.requirements)  # precise: the file names them
        else:
            reqs = {r for c in components for r in architecture.meets.get(c, ())}
        per_file[path] = (reqs, components, bool(source.security))
        if source.kind != "code":
            out.tests.append(path)
            out.links[path] = sorted(reqs)

    def important(uid: str) -> str | None:
        data = ratings.get(uid, {})
        if data.get("criticality") == "high":
            return f"{uid} (criticality high)"
        if data.get("kind") == "security":
            return f"{uid} (security)"
        return None

    def boundaries(components: set[str], every: bool = False) -> list[str]:
        found = []
        for i in architecture.interfaces:
            ends = {i["from"], i["to"]}
            if (every or ends & components) and (i.get("external") or i.get("security_templates")):
                found.append(f"{i['from']} → {i['to']}")
        return sorted(set(found))

    hits: list[str] = []
    crossing: list[str] = []
    for path, (reqs, components, security) in per_file.items():
        found = sorted(filter(None, (important(r) for r in reqs)))
        crosses = boundaries(components)
        if security:
            crosses.append(f"security tests in {path}")
        if found or crosses:
            hits += [f for f in found if f not in hits]
            crossing += [c for c in crosses if c not in crossing]
            if path in out.links:
                out.important_tests.append(path)
    if hits:
        out.reasons.append("touches " + ", ".join(hits))
    if crossing:
        out.reasons.append("crosses a trust boundary: " + ", ".join(crossing))
    if everything:
        every = sorted(filter(None, (important(u) for u in ratings)))
        if every or boundaries(set(), every=True):
            out.reasons.append(
                f"changes {', '.join(everything)}, which traces to no requirement, so it "
                "counts as touching all of them"
            )
    return out


def _weakenings(
    config: ProductConfig, files: list[str], stack: dict | None, base: str
) -> list[Weakening]:
    from tools.read_unit_markers_tool import classify as kind_of

    root = config.root
    code = config.relative(config.code_dir).rstrip("/") + "/"
    test_dirs = [
        config.relative(config.integration_tests_dir),
        config.relative(config.software_tests_dir),
    ]

    def is_test(path: str) -> bool:
        if _under(path, test_dirs):
            return True
        if stack is not None and path.startswith(code):
            return kind_of(path[len(code) :], stack) == "test"
        return False

    found: list[Weakening] = []
    for path in files:
        if not is_test(path):
            continue
        before = file_at(root, base, path)
        if before is None:
            continue  # a new test file
        target = root / path
        if not target.is_file():
            found.append(Weakening(path, "the test file existed", "deleted"))
            continue
        now = target.read_text(encoding="utf-8", errors="replace")
        count_before, count_now = _declared(before), _declared(now)
        if count_now < count_before:
            found.append(
                Weakening(
                    path, f"{count_before} tests", f"{count_before - count_now} test(s) fewer"
                )
            )
        off = _switched_off(root, base, path)
        if off:
            found.append(Weakening(path, "every test ran", f"switched off: {off}"))
    found += _plan_loosened(config, base)
    return found


def _declared(text: str) -> int:
    return sum(1 for line in text.splitlines() if DECLARED.search(line))


def _switched_off(root: Path, base: str, path: str) -> str | None:
    run = subprocess.run(
        ["git", "-C", str(root), "diff", "--unified=0", base, "--", path],
        capture_output=True,
        text=True,
    )
    added = [
        line[1:].strip()
        for line in run.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    hits = [line for line in added if SWITCHED_OFF.search(line)]
    return hits[0] if hits else None


def _plan_values(text: str | None) -> dict[str, float]:
    if not text:
        return {}
    blocks = yaml_blocks_in_text(text, "verification_plan", Path("plan"))
    if len(blocks) != 1 or not isinstance(blocks[0].data, dict):
        return {}
    plan, values = blocks[0].data, {}
    unit = plan.get("unit") or {}
    if isinstance((unit.get("coverage") or {}).get("minimum"), int | float):
        values["unit coverage minimum"] = unit["coverage"]["minimum"]
    for level in ("unit", "integration", "software"):
        budget = (plan.get(level) or {}).get("time_budget") or {}
        for key in ("suite_seconds", "test_seconds"):
            if isinstance(budget.get(key), int | float):
                values[f"{level} time budget {key.replace('_', ' ')}"] = budget[key]
    return values


def _plan_loosened(config: ProductConfig, base: str) -> list[Weakening]:
    path = config.relative(config.verification_plan_file)
    target = config.verification_plan_file
    before = _plan_values(file_at(config.root, base, path))
    now = _plan_values(target.read_text(encoding="utf-8") if target.is_file() else None)
    found = []
    for key, old in before.items():
        new = now.get(key)
        if new is None:
            continue
        lower_is_looser = key == "unit coverage minimum"
        if (new < old) if lower_is_looser else (new > old):
            found.append(Weakening(path, f"{key} {old:g}", f"{key} {new:g}"))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--pull-request", type=int, required=True)
    parser.add_argument("--record", type=Path, help="the review record the review will carry")
    parser.add_argument("--base", help="the ref the change starts after (default: QF_BASE)")
    args = parser.parse_args(argv)
    from tools.read_host_tool import HostError, read_host, repository

    try:
        config = read_product_config(args.root)
    except ConfigError as err:
        print(err.message, file=sys.stderr)
        return 2
    record = None
    if args.record:
        import yaml

        record = yaml.safe_load(args.record.read_text())
        problems = validate(record, "review")
        if problems:
            print(f"{args.record} breaks review.v1: {problems[0].message}", file=sys.stderr)
            return 2
    try:
        repo = repository(config.root)
        pull = read_host().pull_request(repo, args.pull_request)
    except HostError as err:
        print(err, file=sys.stderr)
        return 2
    if pull is None:
        print(f"No pull request {args.pull_request} in {repo}.", file=sys.stderr)
        return 2
    base = resolve_base(config.root, args.base)
    print(json.dumps(classify(config, pull.files, record, base).as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
