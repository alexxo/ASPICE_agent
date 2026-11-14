"""Layer 2 — QUICKSTART names one Python, `python`, as every command calls it.

The agent's runbooks, the CI, the watcher and the sessions' command lines all
call `python`; a guide that checks `python3` passes on a machine where every one
of them fails (FB-75). `python3` stays only where it makes the environment that
provides `python`, and where the agent looks for every Python on the machine.
"""

import re

import pytest

pytestmark = pytest.mark.layer2

ALLOWED = ("python3 -m venv", "which -a python python3", "offer `python3` only")


def test_the_guide_calls_python_as_every_command_does(repo_root):
    text = (repo_root / "QUICKSTART.md").read_text(encoding="utf-8")
    found = [
        f"QUICKSTART.md:{number}: {line.strip()}"
        for number, line in enumerate(text.splitlines(), 1)
        if re.search(r"\bpython3\b", line) and not any(a in line for a in ALLOWED)
    ]
    assert not found, "\n".join(found)
    assert "`python --version`" in text and "`python -c 'import yaml, jsonschema'`" in text
