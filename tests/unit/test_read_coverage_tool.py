"""tools/read_coverage_tool.py — Cobertura XML coverage as percentages."""

import pytest

from tools.read_coverage_tool import CoverageError, read_coverage


def test_the_root_rates_come_back_as_percentages(tmp_path):
    path = tmp_path / "coverage.xml"
    path.write_text('<coverage line-rate="0.8125" branch-rate="0.5" version="7"></coverage>')
    assert read_coverage(path) == {"lines": 81.25, "branches": 50.0}


def test_a_report_that_is_not_cobertura_is_an_error(tmp_path):
    path = tmp_path / "coverage.xml"
    path.write_text("<report></report>")
    with pytest.raises(CoverageError):
        read_coverage(path)


def test_a_file_that_is_not_xml_is_an_error(tmp_path):
    path = tmp_path / "coverage.xml"
    path.write_text("{}")
    with pytest.raises(CoverageError):
        read_coverage(path)
