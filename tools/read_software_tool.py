"""What the stage 8 gates and the verification report share: what proves each
requirement, its threshold, and the values the suites measured.

A constraint is proved by the materials seal and the stack gates; a
requirement with a measurement_method by a value its instrument's suite
measured (decision 6 of the software verification stage); any other by a
passing software-level test marked @sdoc — in the e2e suite for level system,
in the software suite for level software (decisions 3 and 4). Only
requirements that follow requirement.v1 are judged; their form is
check_requirements_contract_gate's to report.
"""

from __future__ import annotations

import json
import operator
import re
from dataclasses import dataclass
from pathlib import Path

from tools.read_product_config_tool import ProductConfig
from tools.read_requirements_tool import RequirementBlock, read_requirements
from tools.validate_contract_tool import validate

__all__ = [
    "Measurement",
    "Threshold",
    "proof",
    "read_measurements",
    "read_threshold",
    "valid_requirements",
]

THRESHOLD = re.compile(r"^(<=|>=|<|>|==)\s*(-?[0-9]+(?:\.[0-9]+)?)\s*(.*)$")
COMPARE = {
    "<=": operator.le,
    ">=": operator.ge,
    "<": operator.lt,
    ">": operator.gt,
    "==": operator.eq,
}


def valid_requirements(config: ProductConfig) -> list[RequirementBlock]:
    return [r for r in read_requirements(config) if not validate(r.data, "requirement")]


def proof(data: dict) -> str:
    """What proves a requirement: 'seal', 'measurement', 'e2e' or 'software'."""
    if data["kind"] == "constraint":
        return "seal"
    if "measurement_method" in data:
        return "measurement"
    return "e2e" if data["level"] == "system" else "software"


@dataclass(frozen=True)
class Threshold:
    op: str
    number: float
    unit: str  # empty when the threshold has none

    def met_by(self, value: float) -> bool:
        return COMPARE[self.op](value, self.number)

    def __str__(self) -> str:
        return f"{self.op} {self.number:g}" + (f" {self.unit}" if self.unit else "")


def read_threshold(text: str) -> Threshold:
    op, number, unit = THRESHOLD.match(text.strip()).groups()
    return Threshold(op, float(number), unit.strip())


@dataclass(frozen=True)
class Measurement:
    requirement: str
    value: float
    unit: str  # empty when the measurement has none
    file: str  # the kept measurements file it came from


def read_measurements(paths: list[Path]) -> tuple[list[Measurement], list[tuple[str, str]]]:
    """The measurements of the kept files, and (file name, problem) for every
    file that is not measurements.v1 JSON."""
    found: list[Measurement] = []
    problems: list[tuple[str, str]] = []
    for path in paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as err:
            problems.append((Path(path).name, f"not JSON: {err}"))
            continue
        violations = validate(data, "measurements")
        if violations:
            first = violations[0]
            problems.append(
                (Path(path).name, f"breaks measurements.v1 at '{first.path}': {first.message}")
            )
            continue
        for entry in data["measurements"]:
            found.append(
                Measurement(
                    entry["requirement"],
                    float(entry["value"]),
                    entry.get("unit", "").strip(),
                    Path(path).name,
                )
            )
    return found, problems
