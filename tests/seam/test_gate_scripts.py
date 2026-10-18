"""The seam — every gate script runs once as a real process, and passes a complete product.

The unit tests call each gate's check() directly; this layer proves what only a
fresh process shows: the script imports when run directly, from another
directory, takes --root, and prints one findings.v1 result under its own name.
The product is complete — through its software verification, tests first, with
its validation scenarios, checkpoints 1 to 3 approved, the verification report
of its tree, delivered in a reviewed pull request — so every gate passes it and
exits 0. It is built once and read by every gate. Gates are discovered from
gates/*/*_gate.py, so a new gate is covered without editing this file.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.validate_contract_tool import validate

ROOT = Path(__file__).resolve().parents[2]
GATES = sorted(ROOT.glob("gates/*/*_gate.py"))


@pytest.fixture(scope="module")
def complete_product(tmp_path_factory):
    """The complete product and the recorded host it is delivered on."""
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

    work = tmp_path_factory.mktemp("seam")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
        root = build_python_product(work / "product")
        for write, message in (
            (write_all_tests_and_stubs, "test(auth): every unit REQ-0047"),
            (write_all_code, "feat(auth): every unit REQ-0047"),
            (write_all_integration_tests, "test(auth): every component and flow REQ-0047"),
            (write_events_code, "feat(auth): the sign-in events REQ-0047"),
            (write_all_software_tests, "test(auth): every requirement REQ-0047"),
            (write_all_scenarios, "test(validation): a scenario for every wish REQ-0047"),
        ):
            write(root)
            commit_all(root, message)
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for checkpoint in (1, 2, 3):
            record_checkpoint(root, checkpoint, "approved", "Alex", "architect", now=when)
        prepare_delivery(root, work, ref="#1")
        host = open_delivery(root, work)
        report = ROOT / "tools" / "write_verification_report_tool.py"
        written = subprocess.run(
            [sys.executable, str(report), "--root", str(root)], capture_output=True, text=True
        )
        assert written.returncode == 0, written.stdout + written.stderr
    return root, host


def test_every_gate_is_discovered():
    assert len(GATES) >= 50, GATES


@pytest.mark.parametrize("script", GATES, ids=[s.stem for s in GATES])
def test_the_gate_script_passes_the_complete_product(complete_product, tmp_path, script):
    root, host = complete_product
    run = subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "QF_HOST_FILE": str(host)},
        timeout=300,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    doc = json.loads(run.stdout)
    assert validate(doc, "findings") == []
    assert doc["gate"] == script.stem
