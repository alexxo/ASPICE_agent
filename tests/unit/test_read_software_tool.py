"""tools/read_software_tool.py — what proves a requirement, thresholds, measurements."""

import json

import pytest

from tools.read_software_tool import proof, read_measurements, read_threshold


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"kind": "constraint", "level": "system"}, "seal"),
        ({"kind": "performance", "level": "software", "measurement_method": {}}, "measurement"),
        ({"kind": "functional", "level": "system"}, "e2e"),
        ({"kind": "interface", "level": "software"}, "software"),
    ],
)
def test_what_proves_a_requirement(data, expected):
    assert proof(data) == expected


@pytest.mark.parametrize(
    ("text", "value", "met"),
    [
        ("<= 200 ms", 200, True),
        ("<= 200 ms", 200.5, False),
        (">= 99.9 %", 99.95, True),
        ("< 5", 5, False),
        ("> 0", 1, True),
        ("== 0 findings", 0, True),
    ],
)
def test_a_threshold_compares_a_value(text, value, met):
    assert read_threshold(text).met_by(value) is met


def test_a_threshold_keeps_its_unit():
    assert read_threshold("<= 200 ms").unit == "ms"
    assert read_threshold("<= 5").unit == ""
    assert str(read_threshold("<= 200 ms")) == "<= 200 ms"


def test_measurements_are_read_and_broken_files_reported(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(
        json.dumps(
            {
                "contract": "measurements.v1",
                "measurements": [{"requirement": "REQ-0060", "value": 180, "unit": "ms"}],
            }
        )
    )
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"contract": "measurements.v1", "measurements": []}))
    found, problems = read_measurements([good, broken, wrong])
    assert [(m.requirement, m.value, m.unit, m.file) for m in found] == [
        ("REQ-0060", 180.0, "ms", "good.json")
    ]
    assert [name for name, _ in problems] == ["broken.json", "wrong.json"]
