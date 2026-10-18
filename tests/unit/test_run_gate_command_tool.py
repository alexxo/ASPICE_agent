"""tools/run_gate_command_tool.py — every gate as a command: --root, findings.v1, exit codes.

The command interface is one piece of code shared by every gate, so its
behaviours are tested once, in-process, with a stand-in check. That each real
gate is wired to it is the seam's (tests/seam/test_gate_scripts.py).
"""

import json

import pytest

from tools.emit_findings_tool import Finding
from tools.run_gate_command_tool import run_gate_command
from tools.validate_contract_tool import validate

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


def test_a_host_that_cannot_be_read_fails_closed(product, capsys):
    from tools.read_host_tool import HostError

    def check(config):
        raise HostError("No QF_HOST_TOKEN")

    code, doc = _command(capsys, check, ["--root", str(product)])
    assert code == 1
    assert validate(doc, "findings") == []
    assert doc["findings"][0]["rule"] == "HOST_UNREADABLE"
    assert "No QF_HOST_TOKEN" in doc["findings"][0]["message"]


def test_wrong_usage_exits_2():
    with pytest.raises(SystemExit) as exit_:
        run_gate_command(STAND_IN, lambda config: [], ["--no-such-flag"])
    assert exit_.value.code == 2
