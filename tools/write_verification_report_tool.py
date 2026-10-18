"""Write the verification report of the current tree (SWE.4 BP5, SWE.5 BP7, SWE.6 BP5).

Runs every verification suite the stack declares — each once per tree, so the
gates' runs are reused — and writes report.json and report.md under
.qf/runs/<tree-hash>/: per unit-test file its passed and failed results; per
component, flow and integration step of the plan; per requirement what proves
it, its software-level tests or measured values next to the threshold, and the
latest result (decision 8 of the software verification stage); per suite how
long it ran and its slowest tests (decision 33 of the unit stages). While a release
is proposed, also per wish its scenarios and their results from the release's
validation record, and the customer's decision (decision 12 of the validation
stage) — the validation suite runs against the deployment, never here — and,
read from the host's issues, the problems and the non-conformances opened,
fixed or closed since the previous release (decision 10 of the problem
resolution stage). The
report records a digest of every suite run it was written from, so
check_verification_report_gate can tell it is current.

    python tools/write_verification_report_tool.py [--root PRODUCT]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_approvals_tool import approval_state  # noqa: E402
from tools.read_commit_range_tool import issue_mentions  # noqa: E402
from tools.read_host_tool import Issue, read_host, repository  # noqa: E402
from tools.read_integration_tool import integration_steps, run_suite  # noqa: E402
from tools.read_product_config_tool import (  # noqa: E402
    ConfigError,
    ProductConfig,
    read_product_config,
)
from tools.read_software_tool import (  # noqa: E402
    proof,
    read_measurements,
    read_threshold,
    valid_requirements,
)
from tools.read_test_results_tool import ResultsError, TestResult, read_results  # noqa: E402
from tools.read_unit_markers_tool import (  # noqa: E402
    scan_integration_tests,
    scan_software_tests,
    scan_sources,
)
from tools.run_stack_commands_tool import (  # noqa: E402
    RUNS_DIR,
    CommandRun,
    read_stack,
    run_command,
    tree_key,
)
from tools.write_release_tool import last_release, pending  # noqa: E402
from tools.write_validation_record_tool import (  # noqa: E402
    read_record,
    read_wishes,
    scan_scenarios,
)

__all__ = [
    "REPORT",
    "report_dir",
    "suite_digest",
    "trend_section",
    "verification_suites",
    "write_report",
]

REPORT = "report.json"
PAGE = "report.md"


def report_dir(config: ProductConfig) -> Path | None:
    """Where the current tree's report lives; None outside git."""
    key = tree_key(config.root)
    return config.root / RUNS_DIR / key if key else None


def suite_digest(run: CommandRun) -> str:
    """A digest of what a suite run produced: its exit code, results and measurements."""
    digest = hashlib.sha256(str(run.exit_code).encode())
    for path in sorted([*run.results, *run.measurements]):
        file = Path(path)
        digest.update(file.name.encode())
        digest.update(file.read_bytes() if file.is_file() else b"")
    return digest.hexdigest()


def _selection(run: CommandRun) -> dict:
    """What the suite ran and why (decision 30 of the unit stages): every test, with
    the reason, or the tests traced to the change, each with its reasons."""
    if run.full:
        why = run.selection["full"] if run.selection else "every test runs"
        return {"full": why}
    return {"full": None, "tests": run.selection["tests"]}


SLOWEST = 5  # the slowest tests the report lists per suite


def _durations(run: CommandRun) -> dict:
    """How long the suite ran, wall clock, and its slowest tests (decision 33)."""
    try:
        results = read_results([Path(p) for p in run.results])
    except ResultsError:
        results = []
    timed = sorted((r for r in results if r.seconds is not None), key=lambda r: -r.seconds)
    slowest = [{"test": r.label, "seconds": r.seconds} for r in timed[:SLOWEST]]
    return {"seconds": run.seconds, "slowest": slowest}


def verification_suites(stack: dict) -> dict[str, dict]:
    """The suites the report runs: every one but validation, which runs against
    the release's deployment."""
    return {name: entry for name, entry in sorted(stack["suites"].items()) if name != "validation"}


def _counts(results: list[TestResult]) -> dict[str, int]:
    return {
        "passed": sum(r.outcome == "passed" for r in results),
        "failed": sum(r.outcome in ("failed", "error") for r in results),
    }


def _merge(counts: list[dict[str, int]]) -> dict[str, int]:
    return {k: sum(c[k] for c in counts) for k in ("passed", "failed")}


def build_report(config: ProductConfig, stack: dict) -> dict:
    runs = {
        name: run_command(config, "suites", name, entry)
        for name, entry in verification_suites(stack).items()
    }
    report: dict = {
        "contract": "verification_report",
        "tree": tree_key(config.root),
        "inputs": {name: suite_digest(run) for name, run in runs.items()},
        "selection": {name: _selection(run) for name, run in runs.items()},
        "durations": {name: _durations(run) for name, run in runs.items()},
    }

    unit_tests = [s for s in scan_sources(config, stack) if s.kind == "test"]
    unit_run = run_suite(config, stack, "unit", unit_tests)
    report["unit"] = [{"file": f, **_counts(rs)} for f, rs in sorted(unit_run.by_file.items())]

    assembled = scan_integration_tests(config, stack)
    integration = run_suite(config, stack, "integration", assembled) if assembled else None
    by_file = integration.by_file if integration else {}
    components: dict[str, list[dict[str, int]]] = {}
    flows: dict[str, list[dict[str, int]]] = {}
    for test in assembled:
        counts = _counts(by_file.get(test.path, []))
        for c in test.components:
            components.setdefault(c, []).append(counts)
        for f in test.flows:
            flows.setdefault(f, []).append(counts)
    passing = integration.passing if integration else set()
    tested = {x for t in assembled if t.path in passing for x in [*t.components, *t.flows]}
    report["integration"] = {
        "components": {c: _merge(v) for c, v in sorted(components.items())},
        "flows": {f: _merge(v) for f, v in sorted(flows.items())},
        "steps": [
            {"step": step["step"], "passed": bool(set(step["selection"]) & tested)}
            for step, _ in integration_steps(config)
        ],
    }

    software = scan_software_tests(config, stack)
    suite_runs = {suite: run_suite(config, stack, suite, software) for suite in ("software", "e2e")}
    measured = {name: read_measurements(run.measurement_paths)[0] for name, run in runs.items()}
    rows = []
    for req in valid_requirements(config):
        data = req.data
        uid, how = data["uid"], proof(data)
        row: dict = {"requirement": uid, "level": data["level"], "kind": data["kind"]}
        if how == "seal":
            row.update(proved_by="materials seal", result="sealed")
        elif how == "measurement":
            suite = data["measurement_method"]["instrument"]
            threshold = read_threshold(data["threshold"])
            values = [
                m
                for m in measured.get(suite, [])
                if m.requirement == uid and m.unit == threshold.unit
            ]
            row.update(
                proved_by="measurement",
                suite=suite,
                threshold=str(threshold),
                measured=[{"value": m.value, "met": threshold.met_by(m.value)} for m in values],
                result="missing"
                if not values
                else "passed"
                if all(threshold.met_by(m.value) for m in values)
                else "failed",
            )
        else:
            run = suite_runs[how]
            mine = [t.path for t in software if uid in t.requirements]
            results = [r for p in mine for r in run.by_file.get(p, [])]
            row.update(
                proved_by="test",
                suite=how,
                tests=mine,
                result="passed"
                if any(p in run.passing for p in mine)
                else "failed"
                if results
                else "missing",
            )
        rows.append(row)
    report["software"] = rows
    versions = pending(config)
    if versions:
        report["validation"] = _validation(config, stack, versions)
        host, repo = read_host(), repository(config.root)
        since = _released_at(config)
        report["problems"] = _problems(host.issues(repo, "problem"), since)
        report["quality"] = _quality(host.issues(repo, "non-conformance"), since)
        report["changes"] = _changes(config, host.issues(repo, "change-request"))
    return report


def _changes(config: ProductConfig, issues: list[Issue]) -> dict:
    """The change requests the release implements — named by a commit since the
    previous release — and those still open (SUP.10 BP6)."""
    last = last_release(config.root)
    named = issue_mentions(config.root, f"{last}..HEAD" if last else "HEAD")
    return {
        "implemented": sorted(i.number for i in issues if i.number in named),
        "open": sorted(i.number for i in issues if i.state == "open"),
    }


def _released_at(config: ProductConfig) -> datetime | None:
    """When the previous release was tagged; None before the first."""
    tag = last_release(config.root)
    if tag is None:
        return None
    run = ["git", "-C", str(config.root), "log", "-1", "--format=%cI", tag]
    return datetime.fromisoformat(
        subprocess.run(run, capture_output=True, text=True).stdout.strip()
    )


def _after(stamp: str | None, since: datetime | None) -> bool:
    return stamp is not None and (since is None or datetime.fromisoformat(stamp) > since)


def _problems(issues: list[Issue], since: datetime | None) -> dict:
    """The problems opened, fixed and still open since the previous release, the
    opened ones by severity and by component (SUP.9 BP7)."""
    opened = [i for i in issues if _after(i.created, since)]
    records = {i.number: i.record("problem")[0] or {} for i in issues}
    fixed = [
        i
        for i in issues
        if records[i.number].get("status") in ("fixed", "closed")
        and (_after(i.closed, since) or i.state == "open")
    ]
    by_component: Counter = Counter()
    for i in opened:
        by_component.update((records[i.number].get("impact") or {}).get("components", []))
    return {
        "since": since.isoformat() if since else None,
        "opened": len(opened),
        "fixed": len(fixed),
        "open": sum(i.state == "open" for i in issues),
        "by_severity": dict(Counter(records[i.number].get("severity", "unknown") for i in opened)),
        "by_component": dict(by_component),
    }


def _quality(issues: list[Issue], since: datetime | None) -> dict:
    """The non-conformances opened, closed and escalated since the previous
    release (SUP.1 BP5)."""
    return {
        "since": since.isoformat() if since else None,
        "opened": sum(_after(i.created, since) for i in issues),
        "closed": sum(_after(i.closed, since) for i in issues),
        "escalated": sum(i.state == "open" and "escalated" in i.labels for i in issues),
    }


def _validation(config: ProductConfig, stack: dict, versions: list[str]) -> list[dict]:
    """Per proposed release, per wish its scenarios and their recorded results,
    and the customer's decision."""
    scenarios = scan_scenarios(config, stack)
    state = approval_state(config, 5, "release")
    releases = []
    for version in versions:
        record, _why = read_record(config, version)
        results = {r["scenario"]: r for r in (record or {}).get("results", [])}
        wishes = []
        for wish in read_wishes(config):
            mine = [s.path for s in scenarios if wish in s.wishes]
            wishes.append(
                {
                    "wish": wish,
                    "scenarios": [
                        {
                            "scenario": path,
                            "technique": results[path]["technique"] if path in results else "",
                            "result": results[path]["result"] if path in results else "missing",
                        }
                        for path in mine
                    ],
                }
            )
        releases.append(
            {
                "release": version,
                "environment": (record or {}).get("environment"),
                "wishes": wishes,
                "decision": state.status,
            }
        )
    return releases


def render(report: dict) -> str:
    lines = [f"# Verification report — tree {report['tree']}", ""]
    lines += ["## What ran", "", "| Suite | Tests | Why |", "|---|---|---|"]
    for suite, chosen in report.get("selection", {}).items():
        if chosen["full"] is not None:
            lines.append(f"| {suite} | every test | {chosen['full']} |")
        elif not chosen["tests"]:
            lines.append(f"| {suite} | none | no test is traced to the change |")
        for test, reasons in (chosen.get("tests") or {}).items():
            lines.append(f"| {suite} | {test} | {'; '.join(reasons)} |")
    lines.append("")
    lines += ["## How long it took", "", "| Suite | Seconds | Slowest tests |", "|---|---|---|"]
    for suite, took in report.get("durations", {}).items():
        seconds = "—" if took["seconds"] is None else f"{took['seconds']:.1f}"
        slowest = "; ".join(f"{t['test']} {t['seconds']:.2f} s" for t in took["slowest"])
        lines.append(f"| {suite} | {seconds} | {slowest or '—'} |")
    lines.append("")
    lines += ["## Unit tests", "", "| Test file | Passed | Failed |", "|---|---|---|"]
    lines += [f"| {u['file']} | {u['passed']} | {u['failed']} |" for u in report["unit"]]
    integ = report["integration"]
    lines += ["", "## Components", "", "| Component | Passed | Failed |", "|---|---|---|"]
    lines += [f"| {c} | {v['passed']} | {v['failed']} |" for c, v in integ["components"].items()]
    lines += ["", "## Flows", "", "| Flow | Passed | Failed |", "|---|---|---|"]
    lines += [f"| {f} | {v['passed']} | {v['failed']} |" for f, v in integ["flows"].items()]
    lines += ["", "## Integration steps", "", "| Step | Tested |", "|---|---|"]
    lines += [f"| {s['step']} | {'yes' if s['passed'] else 'no'} |" for s in integ["steps"]]
    lines += [
        "",
        "## Requirements",
        "",
        "| Requirement | Level | Kind | Proved by | Evidence | Result |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["software"]:
        if r["proved_by"] == "measurement":
            values = ", ".join(f"{m['value']:g}" for m in r["measured"]) or "none"
            evidence = f"{r['suite']}: {values} (threshold {r['threshold']})"
        elif r["proved_by"] == "test":
            evidence = f"{r['suite']}: {', '.join(r['tests']) or 'no test'}"
        else:
            evidence = "checkpoint 3"
        lines.append(
            f"| {r['requirement']} | {r['level']} | {r['kind']} | {r['proved_by']} "
            f"| {evidence} | {r['result']} |"
        )
    for release in report.get("validation", []):
        where = release["environment"]
        place = f"{where['name']}, commit {where['commit'][:12]}" if where else "not deployed"
        lines += [
            "",
            f"## Validation of release {release['release']} — {place}",
            "",
            "| Wish | Scenario | Technique | Result |",
            "|---|---|---|---|",
        ]
        none = [{"scenario": "none", "technique": "", "result": "missing"}]
        for w in release["wishes"]:
            for s in w["scenarios"] or none:
                row = [w["wish"], s["scenario"], s["technique"], s["result"]]
                lines.append(f"| {' | '.join(row)} |")
        lines += ["", f"Customer's decision: {release['decision'].replace('_', ' ')}."]
    if "problems" in report:
        p, q = report["problems"], report["quality"]
        since = p["since"] or "the start"
        lines += [
            "",
            f"## Problems since {since}",
            "",
            f"Opened {p['opened']}, fixed {p['fixed']}, still open {p['open']}.",
            "",
            "| Severity | Opened |",
            "|---|---|",
            *[f"| {s} | {n} |" for s, n in sorted(p["by_severity"].items())],
            "",
            "| Component | Opened |",
            "|---|---|",
            *[f"| {c} | {n} |" for c, n in sorted(p["by_component"].items())],
            "",
            f"## Non-conformances since {since}",
            "",
            f"Opened {q['opened']}, closed {q['closed']}, escalated and open {q['escalated']}.",
        ]
    if "changes" in report:
        c = report["changes"]
        listed = ", ".join(f"#{n}" for n in c["implemented"]) or "none"
        still = ", ".join(f"#{n}" for n in c["open"]) or "none"
        lines += ["", "## Change requests", "", f"Implemented: {listed}. Still open: {still}."]
    return "\n".join(lines) + "\n"


def trend_section(
    config: ProductConfig, key: str, what: str, rule: str = "MISSING_TREND_SECTION"
) -> list:
    """The rule (MISSING_TREND_SECTION by default) when a release is proposed and
    the current tree's report lacks the section; nothing to check otherwise."""
    folder = report_dir(config)
    path = folder / REPORT if folder else None
    if not pending(config) or path is None or not path.is_file():
        return []  # no release, or no report: check_verification_report_gate's
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []  # check_verification_report_gate reports it as stale
    if key in report:
        return []
    return [
        Finding(
            rule,
            config.relative(path),
            None,
            f"A release is proposed, but the report does not count {what}; write it again "
            "with tools/write_verification_report_tool.py.",
        )
    ]


def write_report(config: ProductConfig) -> Path | None:
    """Write the report of the current tree; None without a stack or outside git."""
    stack = read_stack(config)
    folder = report_dir(config)
    if stack is None or folder is None:
        return None
    report = build_report(config, stack)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / REPORT).write_text(json.dumps(report, indent=2))
    (folder / PAGE).write_text(render(report))
    return folder / REPORT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="the product root")
    args = parser.parse_args(argv)
    try:
        config = read_product_config(Path(args.root))
    except ConfigError as err:
        print(f"{err.rule}: {err.message}", file=sys.stderr)
        return 2
    written = write_report(config)
    if written is None:  # nothing to report yet; check_verification_report_gate judges
        print("No report written: the stack is missing or broken, or the product is not in git.")
        return 0
    print(config.relative(written.with_name(PAGE)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
