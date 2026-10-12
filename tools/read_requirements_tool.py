"""Read every requirement block of the product.

Requirements are the ```yaml requirement blocks of the Markdown files under
qf.yaml paths.requirements_dir. Each block comes back with its repository path,
so gates can point findings at it. Blocks that cannot be read are included with
their error: the caller decides how to report them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.read_product_config_tool import ProductConfig
from tools.read_yaml_blocks_tool import YamlBlock, read_yaml_blocks

__all__ = ["RequirementBlock", "read_requirements"]


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
