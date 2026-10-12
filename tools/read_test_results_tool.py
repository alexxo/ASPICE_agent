"""Read JUnit XML test results and tie each result to its test file.

Every suite writes its results as JUnit XML (decision 4). A testcase belongs to
the test file its file attribute names; without one, its classname is read as a
path — com.acme.auth_service.CountFailuresTest is …/com/acme/auth_service/
CountFailuresTest.<ext> — dropping trailing parts until a test file matches, for
a test class inside a module (decision 11). Maven Surefire and pytest (whose
default xunit2 format writes only classname and name) need nothing more.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

__all__ = ["TestResult", "map_to_file", "read_results", "ResultsError"]


class ResultsError(Exception):
    """A results file that is not JUnit XML."""


@dataclass(frozen=True)
class TestResult:
    __test__ = False  # not a pytest test class

    classname: str
    name: str
    file: str | None  # the file attribute, when the runner writes one
    outcome: str  # passed, failed, error or skipped

    @property
    def label(self) -> str:
        return f"{self.classname}.{self.name}" if self.classname else self.name


def read_results(paths: list[Path]) -> list[TestResult]:
    results: list[TestResult] = []
    for path in paths:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as err:
            raise ResultsError(f"{path.name} is not XML: {err}") from err
        for case in root.iter("testcase"):
            results.append(
                TestResult(
                    case.get("classname", ""),
                    case.get("name", ""),
                    case.get("file"),
                    _outcome(case),
                )
            )
    return results


def _outcome(case: ET.Element) -> str:
    tags = {child.tag for child in case}
    if "error" in tags:
        return "error"
    if "failure" in tags:
        return "failed"
    if "skipped" in tags:
        return "skipped"
    return "passed"


def _stem(path: str) -> str:
    p = PurePosixPath(path)
    return p.with_suffix("").as_posix() if p.suffix else p.as_posix()


def _matches(test_file: str, wanted: str) -> bool:
    stem = _stem(test_file)
    return stem == wanted or stem.endswith("/" + wanted)


def map_to_file(result: TestResult, test_files: list[str]) -> str | None:
    """The test file a result belongs to, or None when none matches."""
    if result.file:
        wanted = _stem(result.file.replace("\\", "/").lstrip("./"))
        hits = [f for f in test_files if _matches(f, wanted)]
        if len(hits) == 1:
            return hits[0]
    parts = [p for p in result.classname.split(".") if p]
    for end in range(len(parts), 0, -1):
        wanted = "/".join(parts[:end])
        hits = [f for f in test_files if _matches(f, wanted)]
        if len(hits) == 1:
            return hits[0]
    return None
