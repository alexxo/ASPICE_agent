"""Write the validation record of the proposed release: where it ran, and how every scenario went.

A release is validated on its pull request (decisions 1 and 2 of the
validation stage): after the release record, the product's own pipeline
deploys it to staging — the framework never deploys (decision 4) — and this
tool runs the validation suite, which reaches the deployment the way the
product decides, and writes <qf validation_records_dir>/<version>.yaml
(validation.v1): the environment, the deployed commit, and a result per
automated scenario — pass when every test of its file passed. The results a
person entered for a scenario run by hand are kept while the deployed commit
stays the same; a new deployment starts a new record.

A scenario is a file under qf.yaml paths.validation_scenarios_dir that names a
wish with @wish[W-<n>]; it is automated when it matches the validation suite's
test_files, run by a person otherwise (decision 5). The gates of
stage 11 read the scenarios, the wishes a release affects and the records with
the same functions.

    python tools/write_validation_record_tool.py --environment staging \\
        --commit <deployed sha> [--root PRODUCT]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from tools.read_integration_tool import run_suite  # noqa: E402
from tools.read_product_config_tool import (  # noqa: E402
    ConfigError,
    ProductConfig,
    read_product_config,
)
from tools.read_unit_markers_tool import SourceFile, glob_match  # noqa: E402
from tools.read_yaml_blocks_tool import (  # noqa: E402
    YamlReadError,
    read_yaml_blocks,
    read_yaml_file,
)
from tools.run_stack_commands_tool import read_stack  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402
from tools.write_release_tool import changed_items, pending  # noqa: E402

__all__ = [
    "Scenario",
    "affected_wishes",
    "automated_results",
    "customer_items",
    "plan_entries",
    "read_record",
    "read_wishes",
    "scan_scenarios",
    "validation_record_path",
]

WISH = re.compile(r"@wish\[([^\]\s]+)\]")
AUTOMATED = "acceptance test"  # an automated scenario's technique when the plan names none


@dataclass(frozen=True)
class Scenario:
    path: str  # repository-relative, posix
    automated: bool
    wishes: dict[str, int] = field(default_factory=dict)  # wish ID → first line naming it


def read_wishes(config: ProductConfig) -> dict[str, int]:
    """Every wish ID of the readable wish blocks, with its block's line."""
    if not config.wishes_file.is_file():
        return {}
    wishes: dict[str, int] = {}
    for block in read_yaml_blocks(config.wishes_file, "wish"):
        data = block.data if isinstance(block.data, dict) else {}
        if isinstance(data.get("id"), str):
            wishes.setdefault(data["id"], block.line)
    return wishes


def scan_scenarios(config: ProductConfig, stack: dict | None) -> list[Scenario]:
    """Every file under the scenarios folder that names a wish; hidden folders
    and files that are not UTF-8 text are left out, a file naming no wish is a
    helper."""
    base = config.validation_scenarios_dir
    if not base.is_dir():
        return []
    patterns = (stack or {}).get("validation_test_files", [])
    found = []
    for path in sorted(base.rglob("*")):
        inner = path.relative_to(base)
        if not path.is_file() or any(p.startswith(".") for p in inner.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        wishes: dict[str, int] = {}
        for number, line in enumerate(text.splitlines(), start=1):
            for wish in WISH.findall(line):
                wishes.setdefault(wish, number)
        if wishes:
            automated = glob_match(inner.as_posix(), patterns)
            found.append(Scenario(config.relative(path), automated, wishes))
    return found


def customer_items(config: ProductConfig) -> list[str]:
    """The configuration items of what the customer gets (decision 7): a change to
    any of them affects every wish."""
    paths = [
        config.wishes_file,
        config.diagrams_dir,
        config.requirements_dir,
        config.glossary_file,
        config.architecture_dir,
        config.decisions_dir,
        config.stack_file,
        config.detailed_design_dir,
        config.code_dir,
        config.env_variables_file,
        config.observability_dir,
    ]
    return [config.relative(p) for p in paths]


def affected_wishes(config: ProductConfig) -> set[str]:
    """Every wish when the proposed release changes what the customer gets; none
    when it changes only the framework pin, the tests, the plan, the approvals
    or the records."""
    if set(changed_items(config)) & set(customer_items(config)):
        return set(read_wishes(config))
    return set()


def validation_record_path(config: ProductConfig, version: str) -> Path:
    return config.validation_records_dir / f"{version}.yaml"


def read_record(config: ProductConfig, version: str) -> tuple[dict | None, str | None]:
    """The release's validation record, or None and why it does not count."""
    path = validation_record_path(config, version)
    shown = config.relative(path)
    if not path.is_file():
        return None, f"Release {version} has no validation record ({shown})"
    try:
        record = read_yaml_file(path)
    except YamlReadError as err:
        return None, f"{shown} is not valid YAML: {err.message}"
    violations = validate(record, "validation")
    if violations:
        first = violations[0]
        return None, f"{shown} breaks validation.v1 at '{first.path or 'the record'}': " + (
            first.message
        )
    if record["version"] != version:
        return None, f"{shown} records version {record['version']}, not {version}"
    return record, None


def plan_entries(config: ProductConfig) -> dict[str, dict]:
    """The plan's validation scenarios by path, from a readable plan; its form is
    check_verification_plan_gate's to report."""
    path = config.verification_plan_file
    blocks = read_yaml_blocks(path, "verification_plan") if path.is_file() else []
    data = blocks[0].data if len(blocks) == 1 and isinstance(blocks[0].data, dict) else {}
    section = data.get("validation")
    entries = section.get("scenarios") if isinstance(section, dict) else None
    return {
        e["scenario"]: e
        for e in entries or []
        if isinstance(e, dict) and isinstance(e.get("scenario"), str)
    }


def automated_results(config: ProductConfig, stack: dict, scenarios: list[Scenario]) -> dict:
    """Run the validation suite once for the tree; per automated scenario that
    ran, pass when every one of its tests passed."""
    automated = [SourceFile(s.path, "validation") for s in scenarios if s.automated]
    if not automated:
        return {}
    run = run_suite(config, stack, "validation", automated)
    return {
        path: "pass" if all(r.outcome == "passed" for r in results) else "fail"
        for path, results in run.by_file.items()
        if results
    }


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--environment", required=True, help="where it ran, e.g. staging")
    parser.add_argument("--commit", required=True, help="the commit deployed there")
    args = parser.parse_args(argv)
    try:
        config = read_product_config(args.root)
    except ConfigError as err:
        print(err.message, file=sys.stderr)
        return 2
    versions = pending(config)
    if len(versions) != 1:
        found = ", ".join(versions) if versions else "none"
        print(
            f"Exactly one release must be proposed to validate it (found: {found}); "
            "write its record with tools/write_release_tool.py first.",
            file=sys.stderr,
        )
        return 2
    (version,) = versions
    commit = _git(config.root, "rev-parse", "--verify", "--quiet", f"{args.commit}^{{commit}}")
    if commit.returncode != 0:
        print(f"{args.commit} is no commit of this repository.", file=sys.stderr)
        return 2
    sha = commit.stdout.strip()
    stack = read_stack(config)
    scenarios = scan_scenarios(config, stack)
    techniques = {path: e.get("technique") for path, e in plan_entries(config).items()}
    automated = automated_results(config, stack, scenarios) if stack else {}
    results = [
        {"scenario": s.path, "technique": techniques.get(s.path) or AUTOMATED, "result": result}
        for s in scenarios
        if (result := automated.get(s.path))
    ]
    path = validation_record_path(config, version)
    by_hand = {s.path for s in scenarios if not s.automated}
    previous = yaml.safe_load(path.read_text()) if path.is_file() else None
    if isinstance(previous, dict) and (previous.get("environment") or {}).get("commit") == sha:
        results += [
            r
            for r in previous.get("results") or []
            if isinstance(r, dict) and r.get("scenario") in by_hand
        ]
    record = {
        "contract": "validation.v1",
        "version": version,
        "environment": {"name": args.environment, "commit": sha},
        "results": results,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True))
    print(config.relative(path))
    for path in sorted(by_hand - {r["scenario"] for r in results}):
        print(f"Enter the result of {path}, run by hand, in the record.", file=sys.stderr)
    for s in scenarios:
        if s.automated and s.path not in automated:
            print(f"Automated scenario {s.path} did not run.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
