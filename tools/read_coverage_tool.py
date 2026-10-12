"""Read the code coverage a suite measured, from Cobertura XML.

The unit suite writes its coverage as Cobertura XML (decision 4); the minimum of
the verification plan applies to the whole report, its root line-rate or
branch-rate (decision 16). Rates come back as percentages, 0–100.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

__all__ = ["CoverageError", "read_coverage"]


class CoverageError(Exception):
    """A coverage file that is not Cobertura XML."""


def read_coverage(path: Path) -> dict[str, float]:
    """{'lines': %, 'branches': %} from the report's root element."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as err:
        raise CoverageError(f"{Path(path).name} is not XML: {err}") from err
    if root.tag != "coverage":
        raise CoverageError(f"{Path(path).name} is not Cobertura XML (root <{root.tag}>)")
    rates = {}
    for metric, attribute in (("lines", "line-rate"), ("branches", "branch-rate")):
        try:
            rates[metric] = round(float(root.get(attribute, "")) * 100, 2)
        except ValueError:
            continue
    return rates
