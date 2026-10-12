"""Which skills does the agent load for a stage?

The plugin skill that fills the stage's slot (from qf.yaml, pinned and installed
— the preconditions are checked first), the plugins of the stage's also_slots
(stage 4 asks the diagram plugin for its design diagrams), and the framework
skills of the stage (from agent/stages.yaml). The agent reads all of them before doing the work:
the plugin brings the method, the framework skills bring the form and the rules. A stage
without a slot (stage 10: the agent prepares the release itself) loads no plugin.

    python agent/load_skills_tool.py --stage ID [--root PRODUCT]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.read_config_tool import read_config  # noqa: E402
from agent.read_stages_tool import stage  # noqa: E402

__all__ = ["SKILLS_DIR", "load_skills"]

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def load_skills(root: Path, stage_id: str) -> dict:
    s = stage(stage_id)
    if not s.implemented:
        raise ValueError(f"stage {s.number} ({s.id}) is not implemented yet")
    config, problems = read_config(root)
    if config is None:
        rules = ", ".join(sorted({p.rule for p in problems}))
        raise ValueError(f"pipeline preconditions do not hold: {rules}")
    framework = []
    for name in s.skills:
        (path,) = SKILLS_DIR.glob(f"*/{name}/SKILL.md")
        framework.append(str(path))
    return {
        "stage": s.id,
        "plugin": {
            "slot": s.slot,
            "name": config.product.slots[s.slot],
            "skill_file": str(config.skills[s.slot]),
        }
        if s.slot
        else None,
        "also_plugins": [
            {
                "slot": slot,
                "name": config.product.slots[slot],
                "skill_file": str(config.skills[slot]),
            }
            for slot in s.also_slots
        ],
        "framework_skills": framework,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--stage", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(load_skills(args.root, args.stage), indent=2))
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
