"""Layer 2 — Python is whatever the machine has, `python` or `python3`.

The framework's commands are written `python`; where the machine's name is
`python3`, they run as `python3` (FB-75). The guide checks both names and asks
for no new installation, the runbooks say so, and every session line that may
run Python allows both names.
"""

import re

import pytest

pytestmark = pytest.mark.layer2


def test_the_guide_takes_either_name_and_installs_nothing_new(repo_root):
    text = (repo_root / "QUICKSTART.md").read_text(encoding="utf-8")
    step = text.split("### Step 2")[1].split("### Step 3")[0]
    assert "`python --version`, else `python3 --version`" in step
    assert "install nothing new" in step and "venv" not in text


def test_the_runbooks_name_python3_where_python_is_missing(repo_root):
    for runbook in ("agent/run_aspice_agent.md", "agent/run_reviewer_agent.md"):
        text = " ".join((repo_root / runbook).read_text(encoding="utf-8").split())
        assert "`python3` where `python` is missing" in text, runbook


def test_every_session_line_allows_both_names(repo_root):
    text = (repo_root / "QUICKSTART.md").read_text(encoding="utf-8")
    for line in re.findall(r"^QF_COMMAND_TO_START_\S+=.*$", text, re.M):
        plain = re.findall(r"Bash\(python ([^)]*)", line)
        assert plain == re.findall(r"Bash\(python3 ([^)]*)", line), line
