"""Layer 2 — the command lines of QUICKSTART step 8 start every session, and the
reviewer's line allows every framework tool its runbook runs.

The lines are what the person copies into the two .env files: a line the
launcher cannot read, or a reviewer line missing a tool the runbook names,
stops the sessions of every product that follows the guide.
"""

import re

import pytest

from tools.start_session_tool import SESSIONS, command_for, read_env

pytestmark = pytest.mark.layer2

PERMISSIONS = "--permission-mode dontAsk"


def _lines(repo_root, tmp_path):
    """The step 8 lines, as the launcher reads them from a .env."""
    text = (repo_root / "QUICKSTART.md").read_text(encoding="utf-8")
    step = text.split("### Step 8")[1].split("### Step 9")[0]
    claude = step.split("**With Claude Code**")[1].split("**With another LLM**")[0]
    env = tmp_path / ".env"
    env.write_text("\n".join(re.findall(r"^QF_COMMAND_TO_START_\S+=.*$", claude, re.M)))
    return read_env(env)


def test_every_session_starts_from_the_lines_and_none_is_unrestricted(repo_root, tmp_path):
    values = _lines(repo_root, tmp_path)
    for session in SESSIONS:
        argv = command_for(session, values, "QUICKSTART step 8")("<prompt>")
        assert "<prompt>" in argv and PERMISSIONS in " ".join(argv), session
    fallbacks = {fallback for _, fallback in SESSIONS.values()}
    assert all("--allowedTools" not in values[name] for name in fallbacks)  # read-only


def test_the_reviewer_may_run_every_framework_tool_of_its_runbook(repo_root, tmp_path):
    allowed = command_for("reviewer", _lines(repo_root, tmp_path), "QUICKSTART step 8")("p")[-1]
    runbook = (repo_root / "agent/run_reviewer_agent.md").read_text(encoding="utf-8")
    tools = set(re.findall(r"python <framework>/(\S+\.py)", runbook))
    assert tools
    missing = [t for t in sorted(tools) if f"Bash(python */.framework/{t} *)" not in allowed]
    assert not missing, missing
