"""Build and print a gate result in findings.v1.

Every gate ends by calling emit(): it prints the result as JSON on stdout and
returns the exit code — 0 on pass, 1 on fail. The result is validated against
the findings contract before it is printed, so a gate can never send the retry
loop something it cannot read.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, TextIO

from tools.validate_contract_tool import validate

__all__ = ["Finding", "emit", "result"]


@dataclass(frozen=True)
class Finding:
    """One problem: the gate fills in its own name when the result is built."""

    rule: str  # UPPER_SNAKE_CASE, e.g. UNDEFINED_TERM
    file: str  # repository-relative path
    line: int | None  # 1-based, or None for the whole file
    message: str  # what is wrong and what is expected


def _order(finding: Finding) -> tuple:
    return (finding.file, finding.line or 0, finding.rule, finding.message)


def result(gate: str, findings: list[Finding]) -> dict[str, Any]:
    """The findings.v1 document; raises ValueError if it would break the contract."""
    doc = {
        "gate": gate,
        "result": "fail" if findings else "pass",
        "findings": [
            {"gate": gate, "rule": f.rule, "file": f.file, "line": f.line, "message": f.message}
            for f in sorted(findings, key=_order)
        ],
    }
    violations = validate(doc, "findings")
    if violations:
        first = violations[0]
        raise ValueError(f"gate result breaks findings.v1 at '{first.path}': {first.message}")
    return doc


def emit(gate: str, findings: list[Finding], stream: TextIO | None = None) -> int:
    """Print the result as JSON and return the exit code (0 pass, 1 fail)."""
    doc = result(gate, findings)
    out = stream if stream is not None else sys.stdout
    out.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return 0 if doc["result"] == "pass" else 1
