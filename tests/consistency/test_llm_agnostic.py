"""Layer 2 — the framework names no LLM to run a session, and no secret outside
its one folder.

Every independent session starts with the command the person names in a
.env (tools/start_session_tool.py): no rulebook, prompt, tool or guide may
start one with a given agent's command or restrict it with a given tool's
flags, and the reviewer token lives in ~/.aspice_agent_secrets only. The
changelog records history and is left out; so is the line of the upgrade that
moves the token from its old folder, and an example setting in a .env, where
one agent's command is the person's choice like any other.
"""

import pytest

pytestmark = pytest.mark.layer2

EXCLUDE = (".venv", ".git", "node_modules", ".pytest_cache", "tests")
SUFFIXES = (".md", ".py", ".yml", ".yaml")

FORBIDDEN = ("claude -p", "allowedTools", "aspice_agent_reviewer_bot_token")
HISTORY = ("docs/CHANGELOG.md",)
UPGRADE = "mv ~/.aspice_agent_reviewer_bot_token ~/.aspice_agent_secrets/"


def test_no_session_is_tied_to_one_llm(repo_root):
    found = []
    for path in sorted(repo_root.rglob("*")):
        inner = path.relative_to(repo_root)
        name = inner.as_posix()
        if path.suffix not in SUFFIXES or not path.is_file() or name in HISTORY:
            continue
        if any(part in EXCLUDE for part in inner.parts):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if UPGRADE in line or line.lstrip().startswith("QF_COMMAND_TO_START_"):
                continue
            found += [f"{name}:{number}: {word}" for word in FORBIDDEN if word in line]
    assert not found, "\n".join(found)
