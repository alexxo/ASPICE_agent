"""Read the ASPICE Agent's stage manifest, agent/stages.yaml.

Every agent tool asks this one for the stages, so the order of the V, the gates
of a stage, its skills, its slot and its checkpoint live in data, not in code.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from tools.read_yaml_blocks_tool import read_yaml_file

__all__ = [
    "MANIFEST",
    "Stage",
    "UnknownStage",
    "always_gates",
    "host_gates",
    "flow_stages",
    "read_stages",
    "stage",
]

MANIFEST = Path(__file__).resolve().parent / "stages.yaml"


@dataclass(frozen=True)
class Stage:
    id: str
    number: int
    process: str
    slot: str | None
    also_slots: tuple[str, ...]
    skills: tuple[str, ...]
    gates: tuple[str, ...]
    gates_after_checkpoint: tuple[str, ...]
    planned_gates: tuple[str, ...]
    checkpoint: int | None
    approves: str | None
    implemented: bool
    trigger: str
    checkpoint_on_host: bool = False  # seal 4: a person's review on the host, checked by a gate
    # stages 4 to 7: done only while no requirement changed since their stage done record
    built_from_requirements: bool = False

    @property
    def built_gates(self) -> tuple[str, ...]:
        """Every gate the stage has today, before and after its checkpoint."""
        return self.gates + self.gates_after_checkpoint


@cache
def read_stages() -> tuple[Stage, ...]:
    data = read_yaml_file(MANIFEST)
    return tuple(
        Stage(
            id=s["id"],
            number=s["number"],
            process=s["process"],
            slot=s.get("slot"),
            also_slots=tuple(s.get("also_slots") or ()),
            skills=tuple(s.get("skills") or ()),
            gates=tuple(s.get("gates") or ()),
            gates_after_checkpoint=tuple(s.get("gates_after_checkpoint") or ()),
            planned_gates=tuple(s.get("planned_gates") or ()),
            checkpoint=s.get("checkpoint"),
            approves=s.get("approves"),
            implemented=bool(s["implemented"]),
            trigger=s["trigger"],
            checkpoint_on_host=bool(s.get("checkpoint_on_host", False)),
            built_from_requirements=bool(s.get("built_from_requirements", False)),
        )
        for s in data["stages"]
    )


@cache
def always_gates() -> tuple[str, ...]:
    """The gates that run on every change, whatever stage the product is in."""
    return tuple(read_yaml_file(MANIFEST).get("always_gates") or ())


@cache
def host_gates() -> tuple[str, ...]:
    """The always-on gates that read the code host, so they need one configured."""
    return tuple(read_yaml_file(MANIFEST).get("host_gates") or ())


def flow_stages() -> tuple[Stage, ...]:
    """The stages walked in order (problem and change requests are event-driven)."""
    return tuple(s for s in read_stages() if s.trigger == "flow")


class UnknownStage(ValueError):
    """A --stage that names no stage of the manifest."""


def stage(stage_id: str) -> Stage:
    """The stage named by its id (e.g. diagram) or its number (e.g. 1)."""
    for s in read_stages():
        if stage_id in (s.id, str(s.number)):
            return s
    known = ", ".join(f"{s.number} {s.id}" for s in read_stages())
    raise UnknownStage(f"No stage '{stage_id}'; name one by its id or number: {known}.")
