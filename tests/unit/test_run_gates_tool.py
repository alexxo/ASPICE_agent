"""agent/run_gates_tool.py — runs a stage's gates and collects their findings."""

import json
import subprocess
import sys

import pytest
from product_builder import STACK, baseline_requirements, build_product

from agent.read_stages_tool import stage
from agent.record_checkpoint_tool import record_checkpoint
from agent.run_gates_tool import passed, reached_gates, run_gates
from tools.validate_contract_tool import validate

GATES = ("check_requirements_contract_gate", "check_glossary_gate")


def test_a_passing_product_passes(product):
    results = run_gates(product, GATES)
    assert [r["gate"] for r in results] == list(GATES)
    assert passed(results)


def test_findings_are_collected(tmp_path):
    reqs = baseline_requirements()
    reqs["login"][0]["size"] = "XXL"
    root = build_product(tmp_path, requirements=reqs)
    results = run_gates(root, GATES)
    assert not passed(results)
    assert results[0]["findings"][0]["rule"] == "SCHEMA_VIOLATION"


def test_a_missing_gate_fails_closed(product):
    (result,) = run_gates(product, ["check_nothing_gate"])
    assert result["result"] == "fail"
    assert result["findings"][0]["rule"] == "GATE_MISSING"
    assert validate(result, "findings") == []


def test_a_crashing_gate_fails_closed(product, tmp_path, monkeypatch):
    import agent.run_gates_tool as tool

    gates = tmp_path / "gates" / "swe"
    gates.mkdir(parents=True)
    (gates / "check_crash_gate.py").write_text("raise SystemExit(7)\n")
    monkeypatch.setattr(tool, "GATES_DIR", tmp_path / "gates")
    (result,) = run_gates(product, ["check_crash_gate"])
    assert result["findings"][0]["rule"] == "GATE_CRASHED"


@pytest.mark.parametrize(
    "script",
    [
        'print(\'{"not": "findings"}\')\nraise SystemExit(1)\n',  # JSON that is not findings.v1
        'print(\'{"gate": "check_odd_gate", "result": "pass", "findings": []}\')\n'
        "raise SystemExit(3)\n",  # valid output, unexpected exit code
    ],
)
def test_output_that_is_not_a_gate_result_fails_closed(product, tmp_path, monkeypatch, script):
    import agent.run_gates_tool as tool

    gates = tmp_path / "gates" / "swe"
    gates.mkdir(parents=True)
    (gates / "check_odd_gate.py").write_text(script)
    monkeypatch.setattr(tool, "GATES_DIR", tmp_path / "gates")
    (result,) = run_gates(product, ["check_odd_gate"])
    assert result["findings"][0]["rule"] == "GATE_CRASHED"


def test_runs_a_stage_as_a_command(repo_root, product):
    run = subprocess.run(
        [
            sys.executable,
            str(repo_root / "agent/run_gates_tool.py"),
            "--root",
            str(product),
            "--stage",
            "requirements",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    report = json.loads(run.stdout)
    assert report["result"] == "pass"
    assert [g["gate"] for g in report["gates"]] == list(stage("requirements").gates)


def test_gates_after_a_checkpoint_run_only_once_it_is_approved(tmp_path):
    root = build_product(tmp_path, stack=STACK)
    architecture = stage("architecture")
    assert reached_gates(root, architecture) == architecture.gates
    record_checkpoint(root, 3, "approved", "Alex", "architect")
    assert reached_gates(root, architecture) == architecture.built_gates
