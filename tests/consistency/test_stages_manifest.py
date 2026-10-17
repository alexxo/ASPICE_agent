"""Layer 2 — agent/stages.yaml agrees with the tree.

Every built gate exists as a file, every skill exists, every slot is a
slot of qf.v1, stages are numbered 1–13 in order, and checkpoints 1–5 each close
exactly one stage. A gate cannot be both built and planned for one stage.
"""

import json

import pytest

from agent.read_stages_tool import always_gates, host_gates, read_stages

pytestmark = pytest.mark.layer2


def test_stages_are_numbered_in_order():
    assert [s.number for s in read_stages()] == list(range(1, 14))


def test_every_implemented_gate_exists(repo_root):
    for s in read_stages():
        for gate in s.built_gates:
            assert list(repo_root.glob(f"gates/*/{gate}.py")), f"{s.id}: gate {gate} not found"


def test_a_gate_is_built_or_planned_not_both():
    for s in read_stages():
        assert not set(s.built_gates) & set(s.planned_gates), s.id


def test_gates_after_a_checkpoint_need_one():
    for s in read_stages():
        if s.gates_after_checkpoint:
            assert s.checkpoint, f"{s.id} has gates after a checkpoint it does not have"


def test_every_skill_exists(repo_root):
    for s in read_stages():
        for skill in s.skills:
            assert list(repo_root.glob(f"skills/*/{skill}/SKILL.md")), f"{s.id}: {skill} missing"


def test_every_slot_is_a_qf_slot(repo_root):
    schema = json.loads((repo_root / "contracts/qf_contract.v1.schema.json").read_text())
    slots = set(schema["properties"]["slots"]["properties"])
    for s in read_stages():
        if s.slot:
            assert s.slot in slots, f"{s.id}: unknown slot {s.slot}"


def test_every_also_slot_is_a_qf_slot_other_than_the_stages_own(repo_root):
    qf = json.loads((repo_root / "contracts/qf_contract.v1.schema.json").read_text())
    slots = set(qf["properties"]["slots"]["properties"])
    for s in read_stages():
        for also in s.also_slots:
            assert also in slots, f"stage {s.id}: also_slot {also} is no qf slot"
            assert also != s.slot, f"stage {s.id}: also_slot repeats its own slot"


def test_checkpoints_one_to_five_each_close_one_stage():
    checkpoints = [s.checkpoint for s in read_stages() if s.checkpoint]
    assert sorted(checkpoints) == [1, 2, 3, 4, 5]


def test_an_implemented_stage_has_gates():
    for s in read_stages():
        if s.implemented:
            assert s.gates, f"{s.id} is implemented but has no gate"


def test_every_always_on_gate_exists_and_belongs_to_no_stage(repo_root):
    staged = {g for s in read_stages() for g in (*s.built_gates, *s.planned_gates)}
    for gate in always_gates():
        assert list(repo_root.glob(f"gates/*/{gate}.py")), f"always-on gate {gate} not found"
        assert gate not in staged, f"{gate} is always-on and also a stage's gate"


def test_the_host_gates_are_always_on_gates():
    assert set(host_gates()) <= set(always_gates())
