"""Layer 2 — the diagrams show the flow as it is: a framework test, not a product gate.

The flowchart and the two sequence diagrams of docs/Quality_framework_documentation.md
walk every stage. Asserts, stage by stage, that each names exactly the gates and
the framework skills agent/stages.yaml declares, and that the flowchart and the
detailed sequence name exactly its plugins. The diagram of the agent's inside
has a participant for every tool in agent/. A gate added to a stage, or moved,
fails here until the diagrams follow (decision D65 of Appendix A.1).
"""

import re

import pytest

from agent.read_stages_tool import read_stages

pytestmark = pytest.mark.layer2

DOC = "docs/Quality_framework_documentation.md"
NAME = re.compile(r"\b[a-z][a-z_]*_(gate|skill|plugin)\b")
PARTICIPANT = re.compile(r"^\s*(?:participant|actor) (\w+) as ([a-z_]+)", re.M)
ARROW = re.compile(r"^\s*(\w+)-{1,2}>>(\w+):", re.M)


def _blocks(repo_root):
    return re.findall(r"```mermaid\n(.*?)```", (repo_root / DOC).read_text(), re.S)


def _flowchart(repo_root):
    (block,) = (b for b in _blocks(repo_root) if b.startswith("flowchart") and "subgraph P1[" in b)
    parts = re.split(r"^\s*subgraph P(\d+)\[", block, flags=re.M)[1:]
    pairs = zip(parts[::2], parts[1::2], strict=True)
    return {int(n): body.split("\n  end\n")[0] for n, body in pairs}


def _sequences(repo_root):
    """The two sequence diagrams that walk the stages: stage -> its text, aliases resolved."""
    found = []
    for block in _blocks(repo_root):
        if not block.startswith("sequenceDiagram") or "Note over C,CI: 1 ·" not in block:
            continue
        alias = dict(PARTICIPANT.findall(block))
        parts = re.split(r"Note over C,CI: (\d+) ·", block)[1:]
        stages = {}
        for n, body in zip(parts[::2], parts[1::2], strict=True):
            ends = [alias.get(x, "") for pair in ARROW.findall(body) for x in pair]
            stages[int(n)] = body + "\n" + " ".join(ends)
        found.append(stages)
    return found


def _names(text, kind):
    return {m.group(0) for m in NAME.finditer(text) if m.group(1) == kind}


def _views(repo_root):
    flow = _flowchart(repo_root)
    overview, detailed = _sequences(repo_root)
    return {"flowchart": flow, "overview sequence": overview, "detailed sequence": detailed}


def test_three_diagrams_walk_every_stage(repo_root):
    numbers = {s.number for s in read_stages()}
    for view, stages in _views(repo_root).items():
        assert set(stages) == numbers, f"{view} shows stages {sorted(stages)}"


@pytest.mark.parametrize("kind", ["gate", "skill"])
def test_every_stage_names_its_gates_and_skills(repo_root, kind):
    for view, stages in _views(repo_root).items():
        for s in read_stages():
            expected = (
                {*s.gates, *s.gates_after_checkpoint, *s.planned_gates}
                if kind == "gate"
                else set(s.skills)
            )
            shown = _names(stages[s.number], kind)
            assert shown == expected, (
                f"{view}, stage {s.number}: missing {sorted(expected - shown)}, "
                f"not of this stage {sorted(shown - expected)}"
            )


def test_every_stage_names_its_plugins(repo_root):
    views = _views(repo_root)
    for view in ("flowchart", "detailed sequence"):
        for s in read_stages():
            expected = {*([s.slot] if s.slot else []), *s.also_slots}
            named = _names(views[view][s.number], "plugin")
            shown = {p for p in named if p.startswith(("create_", "review_"))}
            assert (
                shown == expected
            ), f"{view}, stage {s.number}: {sorted(shown)} != {sorted(expected)}"


def test_the_inside_names_every_agent_tool(repo_root):
    (block,) = (b for b in _blocks(repo_root) if "run_aspice_agent<br/>" in b)
    tools = {p.stem for p in (repo_root / "agent").glob("*_tool.py")}
    missing = tools - {name for _, name in PARTICIPANT.findall(block)}
    assert not missing, f"the agent's inside has no participant {sorted(missing)}"
