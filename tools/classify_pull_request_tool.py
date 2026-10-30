"""Classify a pull request: does a person review it, and on what (rule 14 of the
quality assurance stage).

The person decides what is wanted (checkpoints 1 to 3) and whether it was
achieved (checkpoint 4, the results); the build in between is the agents' and
the gates'. So a person is called into a pull request only:

- for the results: it adds or changes software-level tests, so it brings the
  results of software verification — the feature's last pull request (stage
  8); the person approves them requirement by requirement;
- for a question of what is wanted: a test got weaker — a test file deleted,
  fewer tests in a file, a test switched off (skip, xfail, disabled), or the
  verification plan's coverage minimum lowered or a time budget loosened,
  against the base; a finding withdrawn or disputed without a change; the
  reviewer agent asks for a person, for one of five conditions; a story of a
  changed design marks a gap (⚠) the reviewer agent approved, so no
  requirement answers it; or the product's settings change (qf.yaml,
  .gitmodules);
- always for the architecture, and for a checkpoint decision recorded in the
  repository (checkpoints 1, 2, 3 and 5): the person's approval on the host
  confirms the decision is theirs, so no file alone can (FB-68).

Never one chosen by number, and never for the build itself: a changed
detailed design, unit or integration tests and code merge on the reviewer
agent and the gates. The CI file is checked against the framework's template
(verify_required_checks_gate), and a framework pin moved to a released tag by
verify_framework_integrity_gate.

The classification also says what the person reviews and what the watcher
describes before the review: the changed designs, told as stories; the
software-level tests, those of requirements of criticality high or of kind
security first; the requirements they prove; the weakenings, the disputes,
the open questions of the stories and the reviewer agent's request.

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

__all__ = [
    "Classification",
    "Weakening",
    "classify",
    "headline",
    "important",
    "review_record",
    "unsourced",
]

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
    reasons: tuple[str, ...] = ()  # why a person reviews it; empty: no one
    designs: tuple[str, ...] = ()  # components whose detailed design changed: told as stories
    tests: tuple[str, ...] = ()  # software-level tests the person reads with the results
    requirements: dict[str, list[str]] = field(default_factory=dict)  # test file → its REQ-UIDs
    weakenings: tuple[Weakening, ...] = ()
    disputes: tuple[dict, ...] = ()
    request: dict | None = None  # the reviewer agent's own request
    candidates: tuple[str, ...] = ()  # the tests to describe before the review
    brief: tuple[str, ...] = ()  # the reasons in plain words, for the page and the status
    proves: tuple[str, ...] = ()  # the REQ-UIDs whose software-level tests it changes: results
    gaps: tuple[tuple[str, str, str], ...] = ()  # (design, story, step) left open, approved

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
            "candidates": list(self.candidates),
            "brief": list(self.brief),
            "proves": list(self.proves),
            "gaps": [list(g) for g in self.gaps],
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


def unsourced(config: ProductConfig, stories) -> list[str]:
    """Each story step whose source is not in its design, in words: a message of
    the design's sequence diagram, a unit of the design, or a decision its
    document names (D3, ADR-0002)."""
    from adapters.read_archify_diagram_adapter import read_archify_diagrams
    from tools.read_unit_markers_tool import design_units

    units: dict[str, set[str]] = {}
    for unit, (component, _design) in design_units(config).items():
        units.setdefault(component, set()).add(unit)
    messages: dict[str, set[str]] = {}
    for _path, result in read_archify_diagrams(config.detailed_design_dir, config.root):
        diagram = result.diagram
        if diagram is not None and diagram["type"] == "sequence":
            messages[diagram["diagram"]] = {
                e["id"] for e in diagram["elements"] if e["kind"] == "message"
            }
    found = []
    for story in stories:
        design = story["design"]
        document = config.detailed_design_dir / f"{design}.md"
        text = document.read_text(encoding="utf-8") if document.is_file() else ""
        known = {
            "message": messages.get(design, set()),
            "unit": units.get(design, set()),
        }
        for number, step in enumerate(story["steps"], 1):
            for ref in step["source"]:
                kind, _, name = ref.partition(":")
                if kind == "decision":
                    ok = re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text) is not None
                else:
                    ok = name in known.get(kind, set())
                if not ok:
                    found.append(f"'{story['story']}' step {number}: {ref} is not in {design}")
    return found


CHECKPOINT = re.compile(r"-checkpoint-\d+-")  # a decision record, not a stage done record


def always(config: ProductConfig, files) -> str | None:
    """Why every pull request like this one is reviewed by a person, or None."""
    architecture = config.relative(config.architecture_dir).rstrip("/") + "/"
    if any(f.startswith(architecture) for f in files):
        return f"changes the architecture ({architecture})"
    approvals = config.relative(config.approvals_dir).rstrip("/") + "/"
    decisions = [
        f for f in files if f.startswith(approvals) and CHECKPOINT.search(PurePosixPath(f).name)
    ]
    if decisions:
        return f"records a checkpoint decision ({', '.join(decisions)})"
    touched = sorted({".gitmodules", "qf.yaml"} & set(files))
    if touched:
        return f"changes the product's settings ({', '.join(touched)})"
    return None


def classify(
    config: ProductConfig, files, record: dict | None = None, base: str | None = None
) -> Classification:
    """Whether a person reviews the change of these files, why, and on what."""
    files = sorted(set(files))
    reasons: list[str] = []
    brief: list[str] = []
    first = always(config, files)
    if first:
        reasons.append(first)
        brief.append(_ALWAYS_BRIEF[first.split(" (")[0]])
    traced = _trace(config, files)
    if traced.tests:
        reasons.append("brings the results of software verification")
        brief.append("the feature's results are ready for your approval")
    weakenings = _weakenings(config, files, traced.stack, base) if base else []
    for w in weakenings:
        reasons.append(f"weakens a test: {w.file} ({w.now})")
    if weakenings:
        brief.append("a test got weaker")
    record = record or {}
    disputes = tuple(f for f in record.get("findings", []) if f["outcome"] != "fixed")
    if disputes:
        reasons.append(f"{len(disputes)} reviewer finding(s) closed without a change")
        brief.append("the reviewer agent and the author disagree")
    request = record.get("person") if isinstance(record.get("person"), dict) else None
    if request:
        reasons.append(f"the reviewer agent asks for a person: {request['reason']}")
        brief.append("the reviewer agent asks for a person")
    gaps = tuple(
        (story["design"], story["story"], step["text"])
        for story in record.get("stories", [])
        if story["design"] in traced.designs
        for step in story["steps"]
        if step.get("gap")
    )
    if gaps:
        reasons.append(
            f"the design leaves {len(gaps)} question(s) open that no requirement answers"
        )
        brief.append("the design leaves a question open")
    candidates = traced.important_tests or traced.tests
    return Classification(
        tuple(reasons),
        tuple(traced.designs),
        tuple(candidates),
        {t: traced.links.get(t, []) for t in traced.tests},
        tuple(weakenings),
        disputes,
        request,
        tuple(candidates),
        tuple(brief),
        tuple(sorted({u for t in traced.tests for u in traced.links.get(t, [])})),
        gaps,
    )


_ALWAYS_BRIEF = {
    "changes the architecture": "it changes the architecture",
    "records a checkpoint decision": "it records your checkpoint decision",
    "changes the product's settings": "it changes the product's settings",
}


def headline(brief) -> str:
    """The reasons in one short line: the first two, and how many more."""
    shown = list(brief[:2])
    more = len(brief) - len(shown)
    return "; ".join(shown) + (f"; {more} more" if more else "")


def important(data: dict) -> bool:
    """A requirement the architect rated critical or security at checkpoint 2."""
    return data.get("criticality") == "high" or data.get("kind") == "security"


@dataclass
class _Traced:
    designs: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)  # software-level tests changed
    important_tests: list[str] = field(default_factory=list)
    links: dict[str, list[str]] = field(default_factory=dict)
    stack: dict | None = None


def _under(path: str, roots: list[str]) -> bool:
    return any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)


def _trace(config: ProductConfig, files: list[str]) -> _Traced:
    """The changed designs and the software-level tests the change adds or
    changes, with the requirements each test names (@sdoc)."""
    from tools.read_requirements_tool import read_requirements
    from tools.read_unit_markers_tool import scan_software_tests
    from tools.run_stack_commands_tool import read_stack

    out = _Traced()
    out.stack = read_stack(config)
    software = {s.path: s for s in scan_software_tests(config, out.stack)} if out.stack else {}
    ratings = {
        r.data["uid"]: r.data
        for r in read_requirements(config)
        if isinstance(r.data.get("uid"), str)
    }
    design_dir = config.relative(config.detailed_design_dir).rstrip("/") + "/"
    for path in files:
        if path.startswith(design_dir):
            component = PurePosixPath(path).name.split(".")[0]
            if component not in out.designs:
                out.designs.append(component)
            continue
        test = software.get(path)
        if test is None:
            continue
        out.tests.append(path)
        out.links[path] = sorted(test.requirements)
        if any(important(ratings.get(u, {})) for u in test.requirements):
            out.important_tests.append(path)
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
