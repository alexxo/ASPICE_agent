"""agent/record_stage_done_tool.py — a stage without a closing checkpoint, finished once."""

from datetime import datetime, timezone

import pytest
import yaml
from product_builder import STACK, approve_checkpoint, build_product

from agent.record_stage_done_tool import main, record_stage_done
from tools.read_approvals_tool import stage_done_record
from tools.read_product_config_tool import read_product_config
from tools.validate_contract_tool import validate

NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)


def _architecture_passing(tmp_path):
    """Checkpoints 1–3 approved and a complete architecture: stage 3's gates pass."""
    root = build_product(tmp_path, stack=STACK)
    for checkpoint in (1, 2, 3):
        approve_checkpoint(root, checkpoint)
    return root


def test_a_stage_whose_gates_pass_is_recorded(tmp_path):
    root = _architecture_passing(tmp_path)
    path = record_stage_done(root, "3", now=NOW.replace(hour=12))
    assert path.name == "2026-10-04T120000Z-stage-3-done.yaml"
    data = yaml.safe_load(path.read_text())
    assert validate(data, "stage_done") == []
    assert (data["stage"], data["number"]) == ("architecture", 3)
    assert stage_done_record(read_product_config(root), "architecture", 3) == path


def test_a_stage_closed_by_its_checkpoint_is_not_recorded(product):
    with pytest.raises(ValueError, match="closes with checkpoint 1"):
        record_stage_done(product, "diagram")


def test_only_the_current_stage_is_recorded(product):
    with pytest.raises(ValueError, match="not the current stage"):
        record_stage_done(product, "unit_tests")


def test_a_stage_whose_gates_fail_is_not_recorded(tmp_path):
    root = _architecture_passing(tmp_path)
    (root / "docs/architecture/auth-flow.md").unlink()
    with pytest.raises(ValueError, match="its gates still fail"):
        record_stage_done(root, "architecture")


def test_a_stage_waiting_for_its_checkpoint_is_not_recorded(tmp_path):
    root = build_product(tmp_path, stack=STACK)
    for checkpoint in (1, 2):
        approve_checkpoint(root, checkpoint)
    with pytest.raises(ValueError, match="awaits checkpoint 3"):
        record_stage_done(root, "architecture")


def test_the_command_names_an_unknown_stage(product, capsys):
    assert main(["--root", str(product), "--stage", "nine"]) == 2
    assert "No stage 'nine'" in capsys.readouterr().err
