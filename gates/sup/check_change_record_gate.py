"""check_change_record_gate — SUP.10 BP1, BP2: every change request recorded and analysed.

A change request is an issue labelled change-request whose body holds one
```yaml change_request block (change_request.v1; decision 3 of the change
request stage). On every pull request, every change request a commit of the
pull request names (#<n>) has its block (INCOMPLETE_CHANGE_RECORD) and its
analysis — affected items and size (MISSING_CHANGE_ANALYSIS) — and depends only
on change requests (UNKNOWN_DEPENDENCY). While a release is proposed, every
change request is checked, its analysis once past the requested status.

    python gates/sup/check_change_record_gate.py [--root PRODUCT] [--base REV]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_commit_range_tool import issue_mentions, resolve_base  # noqa: E402
from tools.read_host_tool import read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.write_release_tool import pending  # noqa: E402

GATE = "check_change_record_gate"
ANALYSIS = ("affected", "size")


def check(config: ProductConfig, base: str | None = None) -> list[Finding]:
    named = named_in_pull_request(config, base)
    release = bool(pending(config))
    if not named and not release:
        return []
    changes = {i.number: i for i in read_host().issues(repository(config.root), "change-request")}
    wanted = set(changes) if release else set(named) & set(changes)
    findings = []
    for number in sorted(wanted):
        where = f"#{number}"
        record, why = changes[number].record("change_request")
        if record is None:
            findings.append(
                Finding("INCOMPLETE_CHANGE_RECORD", where, None, f"Change request {where}: {why}.")
            )
            continue
        missing = [field for field in ANALYSIS if field not in record]
        if missing and (record["status"] != "requested" or number in named):
            state = "is named by a commit" if number in named else f"is {record['status']}"
            findings.append(
                Finding(
                    "MISSING_CHANGE_ANALYSIS",
                    where,
                    None,
                    f"Change request {where} {state} but states no {', '.join(missing)}; "
                    "analyse it before it is approved.",
                )
            )
        for other in record.get("depends_on", []):
            if other not in changes:
                findings.append(
                    Finding(
                        "UNKNOWN_DEPENDENCY",
                        where,
                        None,
                        f"Change request {where} depends on #{other}, which is no change request.",
                    )
                )
    return findings


def named_in_pull_request(config: ProductConfig, base: str | None = None) -> set[int]:
    """The issue numbers the commits of the pull request name."""
    start = resolve_base(config.root, base)
    return set(issue_mentions(config.root, f"{start}..HEAD" if start else "HEAD"))


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
