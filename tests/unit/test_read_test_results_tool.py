"""tools/read_test_results_tool.py — JUnit XML results tied to their test files."""

import pytest

from tools.read_test_results_tool import ResultsError, TestResult, map_to_file, read_results

XML = """<?xml version="1.0"?>
<testsuites><testsuite name="s">
  <testcase classname="a.test_one" name="test_ok"/>
  <testcase classname="a.test_one" name="test_bad"><failure message="x"/></testcase>
  <testcase classname="a.test_one" name="test_boom"><error message="x"/></testcase>
  <testcase classname="a.test_one" name="test_later"><skipped/></testcase>
</testsuite></testsuites>
"""

FILES = [
    "src/auth_service/test_count_failures.py",
    "src/test/java/com/acme/auth_service/CountFailuresTest.java",
    "src/web_app/test_signin_form.py",
]


def _result(classname, file=None):
    return TestResult(classname, "test_x", file, "passed")


def test_each_testcase_has_its_outcome(tmp_path):
    path = tmp_path / "unit.xml"
    path.write_text(XML)
    outcomes = [(r.name, r.outcome) for r in read_results([path])]
    assert outcomes == [
        ("test_ok", "passed"),
        ("test_bad", "failed"),
        ("test_boom", "error"),
        ("test_later", "skipped"),
    ]


def test_each_testcase_keeps_its_time(tmp_path):
    path = tmp_path / "unit.xml"
    path.write_text(
        '<testsuite><testcase classname="a" name="t1" time="0.25"/>'
        '<testcase classname="a" name="t2"/><testcase classname="a" name="t3" time="x"/>'
        "</testsuite>"
    )
    assert [r.seconds for r in read_results([path])] == [0.25, None, None]


def test_a_file_that_is_not_xml_is_an_error(tmp_path):
    path = tmp_path / "unit.xml"
    path.write_text("not xml")
    with pytest.raises(ResultsError):
        read_results([path])


def test_a_pytest_classname_is_read_as_a_path():
    assert map_to_file(_result("src.auth_service.test_count_failures"), FILES) == FILES[0]
    assert map_to_file(_result("auth_service.test_count_failures"), FILES) == FILES[0]


def test_a_test_class_inside_a_module_drops_the_class():
    result = _result("src.auth_service.test_count_failures.TestLimit")
    assert map_to_file(result, FILES) == FILES[0]


def test_a_java_classname_ends_the_path_under_its_source_root():
    assert map_to_file(_result("com.acme.auth_service.CountFailuresTest"), FILES) == FILES[1]


def test_a_file_attribute_wins():
    result = _result("whatever", file="src/web_app/test_signin_form.py")
    assert map_to_file(result, FILES) == FILES[2]


def test_a_result_matching_no_test_file_is_unmapped():
    assert map_to_file(_result("other.test_thing"), FILES) is None
