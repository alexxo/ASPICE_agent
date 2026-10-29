"""Read every requirement block of the product.

Requirements are the ```yaml requirement blocks of the Markdown files under
qf.yaml paths.requirements_dir. Each block comes back with its repository path,
so gates can point findings at it. Blocks that cannot be read are included with
their error: the caller decides how to report them.

A requirement is critical when its criticality is high or its kind is security:
only a decision a critical requirement depends on is put to the person.
changed_since names the requirements added or changed since a commit, read
from git — what a stage done record of stages 4 to 7 was built against.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.read_product_config_tool import ProductConfig
from tools.read_yaml_blocks_tool import YamlBlock, read_yaml_blocks, yaml_blocks_in_text

__all__ = ["RequirementBlock", "changed_since", "critical", "read_requirements"]


@dataclass(frozen=True)
class RequirementBlock:
    file: str  # repository-relative path
    block: YamlBlock

    @property
    def data(self) -> dict[str, Any]:
        """The block's fields, or {} when it is unreadable or not a mapping."""
        return self.block.data if isinstance(self.block.data, dict) else {}

    def text(self, key: str) -> str | None:
        value = self.data.get(key)
        return value if isinstance(value, str) else None

    def line(self, key: str) -> int:
        """The line of a field, or of the block when the field is absent."""
        return self.block.key_lines.get(key, self.block.line)


def read_requirements(config: ProductConfig) -> list[RequirementBlock]:
    directory = config.requirements_dir
    if not directory.is_dir():
        return []
    return [
        RequirementBlock(config.relative(path), block)
        for path in sorted(directory.rglob("*.md"))
        for block in read_yaml_blocks(path, "requirement")
    ]


def critical(data: dict[str, Any]) -> bool:
    """A requirement the person decides on: criticality high, or kind security."""
    return data.get("criticality") == "high" or data.get("kind") == "security"


def changed_since(config: ProductConfig, commit: str) -> list[str] | None:
    """The UIDs of the requirements added or changed since the commit, in order;
    None when git cannot show the commit (no repository, or not in its history)."""
    then = _requirements_at(config, commit)
    if then is None:
        return None
    now = {r.text("uid"): r.data for r in read_requirements(config) if r.text("uid")}
    return sorted(uid for uid, data in now.items() if then.get(uid) != data)


def _requirements_at(config: ProductConfig, commit: str) -> dict[str, dict] | None:
    folder = config.relative(config.requirements_dir)
    listed = _git(config.root, "ls-tree", "-r", "--name-only", commit, "--", folder)
    if listed is None:
        return None
    found: dict[str, dict] = {}
    for name in listed.splitlines():
        if not name.endswith(".md"):
            continue
        text = _git(config.root, "show", f"{commit}:./{name}")
        for block in yaml_blocks_in_text(text or "", "requirement", Path(name)):
            data = block.data if isinstance(block.data, dict) else {}
            if isinstance(data.get("uid"), str):
                found[data["uid"]] = data
    return found


def _git(root: Path, *args: str) -> str | None:
    run = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    return run.stdout if run.returncode == 0 else None
