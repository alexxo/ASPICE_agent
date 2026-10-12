"""Pipeline preconditions: can the framework run on this product, on this machine?

Checked before any stage, and not gates — they say whether the framework can
run, not whether the product follows a practice:
- qf.yaml exists and follows qf.v1;
- every slot names either a method shipped with the framework
  (quality-framework/<method>, resolved from this framework's plugins/) or a
  skill the agent can find on this machine, so it can load and run it.

Plugins are tools on the machine of whoever runs the agent, not part of the
product, and they may be installed anywhere: for one project, for one user,
system-wide, or wherever an agent host keeps its skills. Where to look is the
machine's business, declared in environment.v1 — <product>/.qf/environment.yaml
first, then ~/.config/quality-framework/environment.yaml — or, without one, the
conventional skill folders. The person installs plugins; the framework never
does, and does not track their versions: the gates prove the work product,
whatever produced it.

    python agent/read_config_tool.py [--root PRODUCT]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import (  # noqa: E402
    CONFIG_FILE,
    ConfigError,
    ProductConfig,
    read_product_config,
)
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

__all__ = ["FRAMEWORK_PLUGIN", "AgentConfig", "environment_files", "read_config"]

FRAMEWORK_PLUGIN = "quality-framework"
FRAMEWORK_PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
PROJECT_ENVIRONMENT = Path(".qf") / "environment.yaml"
USER_ENVIRONMENT = Path(".config") / "quality-framework" / "environment.yaml"
CONVENTIONAL_DIRS = (
    "{root}/.agents/skills",
    "{root}/.claude/skills",
    "~/.agents/skills",
    "~/.claude/skills",
)


@dataclass(frozen=True)
class AgentConfig:
    product: ProductConfig
    skills: dict[str, Path]  # slot -> SKILL.md


def environment_files(root: Path) -> list[Path]:
    """Where an environment file is looked for, in order: the project's, then the user's."""
    return [Path(root) / PROJECT_ENVIRONMENT, Path.home() / USER_ENVIRONMENT]


def read_config(root: Path) -> tuple[AgentConfig | None, list[Finding]]:
    """The configuration when every precondition holds, and the problems otherwise."""
    root = Path(root)
    try:
        product = read_product_config(root)
    except ConfigError as err:
        return None, [err.to_finding()]
    environment, problem = _read_environment(root)
    if problem:
        return None, [problem]
    search = _search_dirs(root, environment)

    problems: list[Finding] = []
    skills: dict[str, Path] = {}
    for slot, name in product.slots.items():
        plugin, _, skill = name.partition("/")
        skill = skill or plugin
        if plugin == FRAMEWORK_PLUGIN:
            shipped = sorted(FRAMEWORK_PLUGINS_DIR.glob(f"*/{skill}/SKILL.md"))
            if shipped:
                skills[slot] = shipped[0]
            else:
                problems.append(
                    _finding(
                        "UNKNOWN_FRAMEWORK_PLUGIN",
                        slot,
                        name,
                        f"the framework ships no method '{skill}' in plugins/",
                    )
                )
            continue
        found = _find(skill, environment, search)
        if found is None:
            looked = ", ".join(d for d, _ in search)
            problems.append(
                _finding(
                    "PLUGIN_NOT_INSTALLED",
                    slot,
                    name,
                    f"no skill '{skill}' was found on this machine (looked in {looked}); install "
                    f"it, or declare where it is in {PROJECT_ENVIRONMENT} or ~/{USER_ENVIRONMENT}",
                )
            )
            continue
        skills[slot] = found
    if problems:
        return None, problems
    return AgentConfig(product, skills), []


def _read_environment(root: Path) -> tuple[dict | None, Finding | None]:
    """The first environment file found, with its folder, or None without one."""
    for path in environment_files(root):
        if not path.is_file():
            continue
        shown = str(PROJECT_ENVIRONMENT) if path == root / PROJECT_ENVIRONMENT else str(path)
        try:
            data = read_yaml_file(path) or {}
        except YamlReadError as err:
            return None, Finding("INVALID_ENVIRONMENT", shown, err.line, err.message)
        violations = validate(data, "environment")
        if violations:
            first = violations[0]
            message = f"Breaks environment.v1 at '{first.path or 'the file'}': {first.message}."
            return None, Finding("INVALID_ENVIRONMENT", shown, None, message)
        return {**data, "_base": path.parent}, None
    return None, None


def _resolve(path: str, base: Path) -> Path:
    resolved = Path(path).expanduser()
    return Path(os.path.normpath(resolved if resolved.is_absolute() else base / resolved))


def _search_dirs(root: Path, environment: dict | None) -> list[tuple[str, Path]]:
    """(as shown, resolved) skill folders: the declared ones first, then the conventional."""
    dirs = []
    if environment:
        dirs += [(d, _resolve(d, environment["_base"])) for d in environment.get("skill_dirs", [])]
    for pattern in CONVENTIONAL_DIRS:
        shown = pattern.replace("{root}", "<product>")
        dirs.append((shown, Path(pattern.replace("{root}", str(root))).expanduser()))
    return dirs


def _find(skill: str, environment: dict | None, search) -> Path | None:
    if environment and skill in environment.get("plugins", {}):
        declared = _resolve(environment["plugins"][skill], environment["_base"])
        return declared if declared.is_file() else None
    for _shown, folder in search:
        candidate = folder / skill / "SKILL.md"
        if candidate.is_file():
            return candidate
    return None


def _finding(rule: str, slot: str, name: str, why: str) -> Finding:
    return Finding(rule, CONFIG_FILE, None, f"Slot {slot} names {name}, but {why}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    config, problems = read_config(args.root)
    report = {
        "ok": config is not None,
        "slots": {k: str(v) for k, v in (config.skills.items() if config else [])},
        "problems": [asdict(p) for p in problems],
    }
    print(json.dumps(report, indent=2))
    return 0 if config else 1


if __name__ == "__main__":
    sys.exit(main())
