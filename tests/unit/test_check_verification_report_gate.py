"""gates/swe/check_verification_report_gate.py — the report is current."""

import json

from product_builder import (
    build_python_product,
    write_all_code,
    write_all_integration_tests,
    write_all_software_tests,
    write_all_tests_and_stubs,
    write_events_code,
)

from gates.swe.check_verification_report_gate import GATE, check
from tools.read_product_config_tool import read_product_config
from tools.write_verification_report_tool import write_report


def _findings(root):
    return check(read_product_config(root))


def _verified(tmp_path):
    root = build_python_product(tmp_path)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    write_events_code(root)
    write_all_integration_tests(root)
    write_all_software_tests(root)
    return root


def test_gate_name_follows_the_convention():
    assert GATE == "check_verification_report_gate"


def test_a_report_of_the_current_tree_passes(tmp_path):
    root = _verified(tmp_path)
    assert write_report(read_product_config(root)) is not None
    assert _findings(root) == []


def test_without_a_report_it_is_missing(tmp_path):
    findings = _findings(_verified(tmp_path))
    assert [f.rule for f in findings] == ["MISSING_REPORT"]
    assert (
        findings[0].file.startswith(".qf/runs/")
        and "write_verification_report" in findings[0].message
    )


def test_a_report_of_an_older_tree_is_missing_for_this_one(tmp_path):
    root = _verified(tmp_path)
    write_report(read_product_config(root))
    write_e2e = root / "st" / "e2e" / "test_more.py"
    write_e2e.write_text("def test_more():\n    assert True\n")
    assert [f.rule for f in _findings(root)] == ["MISSING_REPORT"]


def test_a_report_not_written_from_the_kept_runs_is_stale(tmp_path):
    root = _verified(tmp_path)
    path = write_report(read_product_config(root))
    report = json.loads(path.read_text())
    report["inputs"]["unit"] = "0" * 64
    path.write_text(json.dumps(report))
    findings = _findings(root)
    assert [f.rule for f in findings] == ["STALE_REPORT"]
    assert "unit suite" in findings[0].message


def test_the_report_lists_every_level(tmp_path):
    root = _verified(tmp_path)
    report = json.loads(write_report(read_product_config(root)).read_text())
    assert report["unit"] and all(u["failed"] == 0 for u in report["unit"])
    assert set(report["integration"]["components"]) == {"web-app", "auth-service"}
    assert report["integration"]["flows"]["login"] == {"passed": 2, "failed": 0}
    assert all(s["passed"] for s in report["integration"]["steps"])
    results = {r["requirement"]: r["result"] for r in report["software"]}
    assert results["REQ-0013"] == "sealed" and results["REQ-0047"] == "passed"
    assert set(results.values()) == {"passed", "sealed"}
    assert (path := root / ".qf" / "runs").is_dir() and any(path.rglob("report.md"))


def test_the_report_shows_how_long_each_suite_took(tmp_path):
    root = _verified(tmp_path)
    path = write_report(read_product_config(root))
    report = json.loads(path.read_text())
    unit = report["durations"]["unit"]
    assert unit["seconds"] > 0
    assert unit["slowest"] and len(unit["slowest"]) <= 5
    times = [t["seconds"] for t in unit["slowest"]]
    assert times == sorted(times, reverse=True)
    assert "## How long it took" in path.with_name("report.md").read_text()


def test_a_proposed_release_adds_its_validation_per_wish(tmp_path, monkeypatch):
    from product_builder import (
        DEMO,
        SCENARIO_TESTS,
        build_releasable_product,
        passed,
        propose_release,
        record_validation,
    )

    from tools.write_verification_report_tool import PAGE

    root, host = build_releasable_product(tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    propose_release(root)
    record_validation(root, passed(SCENARIO_TESTS["W-01"]))
    written = write_report(read_product_config(root))
    report = json.loads(written.read_text())
    assert "validation" not in report["inputs"]  # it runs against the deployment
    (release,) = report["validation"]
    assert (release["release"], release["decision"]) == ("1.0.0", "missing")
    assert release["wishes"][1] == {
        "wish": "W-02",
        "scenarios": [{"scenario": DEMO, "technique": "", "result": "missing"}],
    }
    assert "## Validation of release 1.0.0 — staging" in written.with_name(PAGE).read_text()
    assert _findings(root) == []
