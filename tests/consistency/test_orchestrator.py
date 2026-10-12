"""Layer 2 — the orchestrator carries ODD's steps and calls only tools that exist.

ODD's steps 1, 4 and 5 (Authorize, Classify, Track before write) and its close
are the same at every stage, so the orchestrator — not each method — holds them.
Every agent tool it tells the agent to run must exist in this tree.
"""

import re

import pytest

pytestmark = pytest.mark.layer2

ORCHESTRATOR = "agent/run_aspice_agent.md"
ODD_SECTIONS = ["Authorize", "Classify", "Track before write", "Close"]


def _text(repo_root):
    return (repo_root / ORCHESTRATOR).read_text()


def test_odd_steps_are_sections_of_the_orchestrator(repo_root):
    text = _text(repo_root)
    for section in ODD_SECTIONS:
        assert re.search(rf"^## \d+\. {re.escape(section)}\s*$", text, re.M), section


def test_the_feature_document_is_the_temporary_one(repo_root):
    assert ".qf/tasks/<feature>.md" in _text(repo_root)


def test_every_tool_the_orchestrator_runs_exists(repo_root):
    tools = set(re.findall(r"<framework>/(agent/[\w]+\.py)", _text(repo_root)))
    assert tools, "the orchestrator runs no tool"
    for tool in tools:
        assert (repo_root / tool).is_file(), f"{ORCHESTRATOR} runs {tool}, which does not exist"


def test_no_provider_specific_tool_is_used(repo_root):
    assert not re.search(r"engram|openspec|\.atl/|gentle-ai", _text(repo_root), re.IGNORECASE)


def test_the_agent_never_installs_plugins_itself(repo_root):
    """The person keeps control of what is installed on their machine: the
    orchestrator relays the install commands from the finding, never runs any."""
    text = _text(repo_root)
    assert "Never install, update or remove a plugin yourself" in text
    # no install command of its own: it relays the finding's commands to the person
    assert not re.search(r"git clone|cp -R|npx |pip install|install_plugins", text)
