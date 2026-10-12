"""Read the fenced YAML blocks of a Markdown file, and plain YAML files.

Requirement and glossary files are Markdown whose contract lives in fenced
blocks tagged with the record name (```yaml requirement, ```yaml glossary_term).
Each block comes back with the line it starts on and the line of each top-level
field, so a finding can point at the exact place. A block that cannot be read is
returned with its error, never skipped: a gate that skipped it would pass
without checking it.

YAML is read in the JSON data model: timestamps stay strings, so every value is
checked as the JSON value a schema expects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "YamlBlock",
    "YamlReadError",
    "load_json_yaml",
    "read_yaml_blocks",
    "read_yaml_file",
    "yaml_blocks_in_text",
]

_TIMESTAMP = "tag:yaml.org,2002:timestamp"


class _JsonModelLoader(yaml.SafeLoader):
    """SafeLoader without the implicit timestamp type."""


_JsonModelLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag != _TIMESTAMP]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


class YamlReadError(Exception):
    """A YAML file that cannot be parsed; line is 1-based, or None if unknown."""

    def __init__(self, file: Path, line: int | None, message: str):
        super().__init__(f"{file}:{line}: {message}" if line else f"{file}: {message}")
        self.file = file
        self.line = line
        self.message = message


@dataclass(frozen=True)
class YamlBlock:
    """One fenced block. data is None when error is set."""

    file: Path
    line: int
    data: Any
    key_lines: dict[str, int] = field(default_factory=dict)
    error: str | None = None


def load_json_yaml(text: str) -> Any:
    """Parse YAML text in the JSON data model (a SafeLoader: no arbitrary objects)."""
    return yaml.load(text, Loader=_JsonModelLoader)


def read_yaml_file(path: Path) -> Any:
    """Parse a whole YAML file; raise YamlReadError with the line on failure."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        return load_json_yaml(text)
    except yaml.YAMLError as err:
        line, message = _describe(err, text)
        raise YamlReadError(Path(path), line, message) from err


def read_yaml_blocks(path: Path, tag: str) -> list[YamlBlock]:
    """Every ```yaml <tag> block of a Markdown file, in file order."""
    path = Path(path)
    return yaml_blocks_in_text(path.read_text(encoding="utf-8"), tag, path)


def yaml_blocks_in_text(text: str, tag: str, source: Path) -> list[YamlBlock]:
    """Every ```yaml <tag> block of a Markdown text (e.g. an issue's body), in
    order; source names where the text came from."""
    path = Path(source)
    lines = text.splitlines()
    opening = re.compile(rf"^```yaml\s+{re.escape(tag)}\s*$")
    blocks: list[YamlBlock] = []
    i = 0
    while i < len(lines):
        if not opening.match(lines[i]):
            i += 1
            continue
        start = i + 1  # 0-based index of the first content line
        end = next((j for j in range(start, len(lines)) if lines[j].startswith("```")), None)
        if end is None:
            blocks.append(YamlBlock(path, start + 1, None, error="block is not closed with ```"))
            break
        blocks.append(_parse_block(path, "\n".join(lines[start:end]), start + 1))
        i = end + 1
    return blocks


def _parse_block(path: Path, text: str, first_line: int) -> YamlBlock:
    try:
        data = load_json_yaml(text)
        node = yaml.compose(text, Loader=_JsonModelLoader)
    except yaml.YAMLError as err:
        line, message = _describe(err, text)
        return YamlBlock(path, first_line + (line - 1 if line else 0), None, error=message)
    key_lines: dict[str, int] = {}
    if isinstance(node, yaml.MappingNode):
        for key, _value in node.value:
            key_lines[str(key.value)] = first_line + key.start_mark.line
    return YamlBlock(path, first_line, data, key_lines)


def _describe(err: yaml.YAMLError, text: str) -> tuple[int | None, str]:
    """The 1-based line of the problem and its description.

    PyYAML reports an unclosed value at the end of the stream, which can fall on
    the empty line after a final newline; that is clamped to the last line with
    content, where the broken value is.
    """
    mark = getattr(err, "problem_mark", None)
    line = mark.line + 1 if mark is not None else None
    if line is not None:
        content = text.splitlines()
        last = max((i + 1 for i, s in enumerate(content) if s.strip()), default=1)
        line = min(line, last)
    problem = getattr(err, "problem", None) or str(err)
    return line, problem
