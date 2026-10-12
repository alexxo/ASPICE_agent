"""verify_acceptance_to_wishes_link_gate — VAL.1 BP1, BP2, BP4: every wish has its scenario.

A scenario is a file under qf.yaml paths.validation_scenarios_dir that names a
wish with @wish[W-<n>] (decision 5 of the validation stage). On every pull
request, every wish has at least one scenario (MISSING_SCENARIO) and every
marker names a wish that exists (UNKNOWN_WISH): validation is specified in
advance, so the scenarios arrive with the deliveries (decision 6). While a
release is proposed, every wish it affects that has a scenario has one with a
result in the release's validation record (UNVALIDATED_WISH); a release affects
every wish when it changes what the customer gets, none otherwise (decision 7).
A record that cannot be read is verify_release_evidence_gate's to report.

    python gates/val/verify_acceptance_to_wishes_link_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402
from tools.write_release_tool import pending  # noqa: E402
from tools.write_validation_record_tool import (  # noqa: E402
    affected_wishes,
    read_record,
    read_wishes,
    scan_scenarios,
)

GATE = "verify_acceptance_to_wishes_link_gate"


def check(config: ProductConfig) -> list[Finding]:
    wishes = read_wishes(config)
    if not wishes:
        return []  # verify_diagram_to_wishes_link_gate reports a product without wishes
    wishes_file = config.relative(config.wishes_file)
    folder = config.relative(config.validation_scenarios_dir)
    scenarios = scan_scenarios(config, read_stack(config))
    findings = []
    for s in scenarios:
        for wish, line in s.wishes.items():
            if wish not in wishes:
                findings.append(
                    Finding(
                        "UNKNOWN_WISH",
                        s.path,
                        line,
                        f"Scenario {s.path} names wish {wish}, which is not in {wishes_file}.",
                    )
                )
    by_wish: dict[str, set[str]] = {}
    for s in scenarios:
        for wish in s.wishes:
            by_wish.setdefault(wish, set()).add(s.path)
    for wish, line in wishes.items():
        if wish not in by_wish:
            findings.append(
                Finding(
                    "MISSING_SCENARIO",
                    wishes_file,
                    line,
                    f"Wish {wish} has no validation scenario; the village crew writes one, "
                    f"marked @wish[{wish}], under {folder}.",
                )
            )
    versions = pending(config)
    if versions:
        findings += _coverage(config, versions, by_wish)
    return findings


def _coverage(config, versions, by_wish) -> list[Finding]:
    affected = affected_wishes(config)
    findings = []
    for version in versions:
        record, _why = read_record(config, version)
        if record is None:
            continue
        ran = {r["scenario"] for r in record["results"]}
        for wish in sorted(affected):
            if wish in by_wish and not by_wish[wish] & ran:
                findings.append(
                    Finding(
                        "UNVALIDATED_WISH",
                        config.relative(config.validation_records_dir / f"{version}.yaml"),
                        None,
                        f"Release {version} affects wish {wish}, but none of its scenarios "
                        f"({', '.join(sorted(by_wish[wish]))}) has a result in the record.",
                    )
                )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
