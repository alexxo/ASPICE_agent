"""Layer 2 — the rulebook is complete (SUP.1 BP2): a framework test, not a product gate.

The rulebook is the practice table of docs/Quality_framework_documentation.md:
every practice names the gate that checks it (**Gate:** …). Asserts: every gate
script belongs to a practice, and every gate a practice names is a script or a
planned gate of a stage in agent/stages.yaml — so no practice points at a gate
nobody will build, and no gate checks something no practice asks for
(decision 10 of the quality assurance stage).
"""

import re

import pytest

from agent.read_stages_tool import read_stages

pytestmark = pytest.mark.layer2

DOC = "docs/Quality_framework_documentation.md"


def _named(repo_root):
    return set(re.findall(r"\*\*Gate:\*\* ([a-z_]+_gate)\b", (repo_root / DOC).read_text()))


def _scripts(repo_root):
    return {p.stem for p in (repo_root / "gates").glob("*/*_gate.py")}


def test_every_gate_script_belongs_to_a_practice(repo_root):
    orphans = _scripts(repo_root) - _named(repo_root)
    assert not orphans, f"gates no practice names: {sorted(orphans)}"


def test_every_gate_a_practice_names_is_built_or_planned(repo_root):
    planned = {g for s in read_stages() for g in s.planned_gates}
    missing = _named(repo_root) - _scripts(repo_root) - planned
    assert not missing, f"practices name gates neither built nor planned: {sorted(missing)}"


def test_every_gate_a_stage_runs_is_built(repo_root):
    built = {g for s in read_stages() for g in s.built_gates}
    assert built <= _scripts(repo_root), sorted(built - _scripts(repo_root))
