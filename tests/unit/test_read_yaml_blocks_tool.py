"""tools/read_yaml_blocks_tool.py — reads the fenced YAML blocks of a Markdown file."""

import pytest

from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_blocks, read_yaml_file

REQUIREMENTS = """\
# Login

Free prose.

```yaml requirement
uid: REQ-0012
statement: A user signs in.
```

```yaml glossary_term
term: account
definition: One user's record.
```

```yaml
plain: not tagged
```

```yaml requirement
uid: REQ-0013
date: 2026-10-04T10:00:00Z
```
"""


def _write(tmp_path, text, name="login.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_only_blocks_with_the_tag_are_read(tmp_path):
    blocks = read_yaml_blocks(_write(tmp_path, REQUIREMENTS), "requirement")
    assert [b.data["uid"] for b in blocks] == ["REQ-0012", "REQ-0013"]


def test_block_line_is_the_first_content_line(tmp_path):
    first, second = read_yaml_blocks(_write(tmp_path, REQUIREMENTS), "requirement")
    assert (first.line, second.line) == (6, 20)


def test_key_lines_point_at_each_top_level_field(tmp_path):
    first = read_yaml_blocks(_write(tmp_path, REQUIREMENTS), "requirement")[0]
    assert first.key_lines == {"uid": 6, "statement": 7}


def test_timestamps_stay_strings(tmp_path):
    second = read_yaml_blocks(_write(tmp_path, REQUIREMENTS), "requirement")[1]
    assert second.data["date"] == "2026-10-04T10:00:00Z"


def test_a_file_without_blocks_gives_none(tmp_path):
    assert read_yaml_blocks(_write(tmp_path, "# Nothing here\n"), "requirement") == []


def test_broken_yaml_is_reported_not_skipped(tmp_path):
    text = "```yaml requirement\nuid: REQ-0001\nstatement: [unclosed\n```\n"
    (block,) = read_yaml_blocks(_write(tmp_path, text), "requirement")
    assert block.data is None
    assert block.error and block.line == 3  # the line holding the broken value


def test_unclosed_fence_is_reported(tmp_path):
    text = "intro\n```yaml requirement\nuid: REQ-0001\n"
    (block,) = read_yaml_blocks(_write(tmp_path, text), "requirement")
    assert block.data is None
    assert "not closed" in block.error
    assert block.line == 3


def test_value_starting_with_asterisk_is_a_parse_error(tmp_path):
    """Why domain terms are marked with underscores, not asterisks."""
    text = "```yaml requirement\nstatement: *lockout* happens\n```\n"
    (block,) = read_yaml_blocks(_write(tmp_path, text), "requirement")
    assert block.error


def test_read_yaml_file_returns_json_model_data(tmp_path):
    path = _write(tmp_path, "checkpoint: 2\ndate: 2026-10-04T10:00:00Z\n", "approval.yaml")
    assert read_yaml_file(path) == {"checkpoint": 2, "date": "2026-10-04T10:00:00Z"}


def test_read_yaml_file_raises_with_the_line(tmp_path):
    path = _write(tmp_path, "a: 1\nb: [unclosed\n", "broken.yaml")
    with pytest.raises(YamlReadError) as err:
        read_yaml_file(path)
    assert err.value.line == 2
    assert err.value.file == path
