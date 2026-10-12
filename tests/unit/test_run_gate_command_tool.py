"""tools/run_gate_command_tool.py — every gate as a command: --root, findings.v1, exit codes.

The command interface is one piece of code shared by every gate, so its
behaviours are tested once, in-process, with a stand-in check. Each real gate
then gets one check that it is wired to that interface: run as a command from
another directory, it prints findings.v1 under its own name and exits 0 on a
passing product. Gates are discovered from gates/*/*_gate.py, so a new gate is
covered without editing this file.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.emit_findings_tool import Finding
from tools.run_gate_command_tool import run_gate_command
from tools.validate_contract_tool import validate

ROOT = Path(__file__).resolve().parents[2]
GATES = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob("gates/*/*_gate.py"))
STAND_IN = "check_stand_in_gate"


def _command(capsys, check, argv):
    code = run_gate_command(STAND_IN, check, argv)
    return code, json.loads(capsys.readouterr().out)


# ── the shared interface, tested once ───────────────────────────────────────


def test_no_findings_print_a_pass_and_exit_0(product, capsys):
    code, doc = _command(capsys, lambda config: [], ["--root", str(product)])
    assert code == 0
    assert doc == {"gate": STAND_IN, "result": "pass", "findings": []}


def test_findings_print_a_fail_and_exit_1(product, capsys):
    finding = Finding("SOME_RULE", "qf.yaml", None, "Something is wrong.")
    code, doc = _command(capsys, lambda config: [finding], ["--root", str(product)])
    assert code == 1
    assert validate(doc, "findings") == []
    assert doc["findings"][0]["rule"] == "SOME_RULE"


def test_the_check_receives_the_products_configuration(product, capsys):
    seen = []
    _command(capsys, lambda config: seen.append(config.root) or [], ["--root", str(product)])
    assert seen == [product]


def test_root_defaults_to_the_current_directory(product, capsys, monkeypatch):
    monkeypatch.chdir(product)
    seen = []
    _command(capsys, lambda config: seen.append(config.root) or [], [])
    assert seen[0].resolve() == product.resolve()


def test_a_missing_config_fails_closed_without_running_the_check(tmp_path, capsys):
    ran = []
    code, doc = _command(capsys, lambda config: ran.append(1) or [], ["--root", str(tmp_path)])
    assert code == 1
    assert doc["findings"][0]["rule"] == "MISSING_CONFIG"
    assert ran == []


def test_a_check_taking_base_receives_it(product, capsys):
    seen = []

    def check(config, base=None):
        seen.append(base)
        return []

    _command(capsys, check, ["--root", str(product), "--base", "origin/main"])
    _command(capsys, check, ["--root", str(product)])
    assert seen == ["origin/main", None]


def test_wrong_usage_exits_2():
    with pytest.raises(SystemExit) as exit_:
        run_gate_command(STAND_IN, lambda config: [], ["--no-such-flag"])
    assert exit_.value.code == 2


# ── each real gate is wired to it ───────────────────────────────────────────


def test_every_gate_is_discovered():
    assert len(GATES) >= 6, GATES


@pytest.fixture
def complete_product(tmp_path, monkeypatch):
    """A product through its software verification, tests first, and its
    validation scenarios, with checkpoints 1 to 3 approved and the verification
    report of its tree, delivered in a reviewed pull request."""
    from product_builder import (
        build_python_product,
        commit_all,
        open_delivery,
        prepare_delivery,
        write_all_code,
        write_all_integration_tests,
        write_all_scenarios,
        write_all_software_tests,
        write_all_tests_and_stubs,
        write_events_code,
    )

    from agent.record_checkpoint_tool import record_checkpoint

    root = build_python_product(tmp_path / "product")
    write_all_tests_and_stubs(root)
    commit_all(root, "test(auth): every unit REQ-0047")
    write_all_code(root)
    commit_all(root, "feat(auth): every unit REQ-0047")
    write_all_integration_tests(root)
    commit_all(root, "test(auth): every component and flow REQ-0047")
    write_events_code(root)
    commit_all(root, "feat(auth): the sign-in events REQ-0047")
    write_all_software_tests(root)
    commit_all(root, "test(auth): every requirement REQ-0047")
    write_all_scenarios(root)
    commit_all(root, "test(validation): a scenario for every wish REQ-0047")
    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for checkpoint in (1, 2):
        record_checkpoint(root, checkpoint, "approved", "Alex", "architect", now=when)
    record_checkpoint(root, 3, "approved", "Alex", "architect", now=when)
    prepare_delivery(root, tmp_path, ref="#1")
    monkeypatch.setenv("QF_HOST_FILE", str(open_delivery(root, tmp_path)))
    report = Path(__file__).resolve().parents[2] / "tools" / "write_verification_report_tool.py"
    written = subprocess.run(
        [sys.executable, str(report), "--root", str(root)], capture_output=True, text=True
    )
    assert written.returncode == 0, written.stdout + written.stderr
    return root


@pytest.mark.parametrize("gate", GATES)
def test_each_gate_runs_as_a_command(repo_root, complete_product, tmp_path_factory, gate):
    product = complete_product
    run = subprocess.run(
        [sys.executable, str(repo_root / gate), "--root", str(product)],
        capture_output=True,
        text=True,
        cwd=tmp_path_factory.mktemp("elsewhere"),
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    doc = json.loads(run.stdout)
    assert validate(doc, "findings") == []
    assert doc["gate"] == Path(gate).stem
