"""agent/record_stage_done_tool.py — a stage without a closing checkpoint, finished once."""

from datetime import datetime, timezone

import pytest
import yaml
from product_builder import STACK, build_product

from agent.record_checkpoint_tool import record_checkpoint
from agent.record_stage_done_tool import main, record_stage_done
from tools.read_approvals_tool import stage_done_record
from tools.read_product_config_tool import read_product_config
from tools.validate_contract_tool import validate

NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)


def _architecture_passing(tmp_path):
    """Checkpoints 1–3 approved and a complete architecture: stage 3's gates pass."""
    root = build_product(tmp_path, stack=STACK)
    for checkpoint, hour in ((1, 9), (2, 10), (3, 11)):
        record_checkpoint(
            root, checkpoint, "approved", "Alex", "architect", now=NOW.replace(hour=hour)
        )
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
    for checkpoint, hour in ((1, 9), (2, 10)):
        record_checkpoint(
            root, checkpoint, "approved", "Alex", "architect", now=NOW.replace(hour=hour)
        )
    with pytest.raises(ValueError, match="awaits checkpoint 3"):
        record_stage_done(root, "architecture")


def test_the_command_names_an_unknown_stage(product, capsys):
    assert main(["--root", str(product), "--stage", "nine"]) == 2
    assert "No stage 'nine'" in capsys.readouterr().err


# --- a stage built from the requirements, recorded again after a change request (FB-63) --


def _decided(tmp_path, *records):
    import copy

    from product_builder import DECISIONS, baseline_requirements

    requirements = baseline_requirements()
    for records_of_file in requirements.values():
        for req in records_of_file:
            if req["uid"] == "REQ-0011":
                req["criticality"] = "low"
    decisions = copy.deepcopy(DECISIONS)
    for record in records:
        decisions[f"{record['id'][4:]}-record"] = copy.deepcopy(record)
    root = build_product(
        tmp_path, stack=STACK, decisions=decisions, requirements=requirements, git=False
    )
    return read_product_config(root)


PREVIOUS = {"date": "2026-10-28T08:00:00+00:00"}


def test_each_changed_requirement_needs_a_decision_since_the_record(tmp_path):
    from product_builder import AGENT_DECISION

    from agent.record_stage_done_tool import _undecided

    config = _decided(tmp_path, AGENT_DECISION)
    assert _undecided(config, ["REQ-0011"], PREVIOUS) == []
    missing = _undecided(config, ["REQ-0011"], {"date": "2026-10-30T08:00:00+00:00"})
    assert missing == ["REQ-0011: no decision record serves it (decided_by agent)"]


def test_a_critical_changed_requirement_needs_the_person_s_answer(tmp_path):
    from product_builder import PERSON_DECISION

    from agent.record_stage_done_tool import _undecided

    config = _decided(tmp_path, PERSON_DECISION)
    [missing] = _undecided(config, ["REQ-0012"], PREVIOUS)
    assert missing.startswith("REQ-0012 is critical: the person decides")
    answered = {**PERSON_DECISION, "status": "accepted", "answered_by": "Alex"}
    config = _decided(tmp_path / "answered", answered)
    assert _undecided(config, ["REQ-0012"], PREVIOUS) == []
