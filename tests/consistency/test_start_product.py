"""Layer 2 — the start rulebook asks every value the setup requires and hands over.

The person starts a product by telling the agent to follow agent/start_product.md;
it must pass every flag create_product_tool requires, run only files that exist,
and end in the orchestrator.
"""

import re

import pytest

pytestmark = pytest.mark.layer2

RULEBOOK = "agent/start_product.md"
TOOL = "tools/create_product_tool.py"


def _text(repo_root):
    return (repo_root / RULEBOOK).read_text()


def test_every_required_flag_of_the_setup_is_asked(repo_root):
    source = (repo_root / TOOL).read_text()
    flags = set(re.findall(r'\(\s*"(--[a-z]+(?:-[a-z]+)*)",', source)) - {"--root"}
    assert flags, f"{TOOL} declares no flag"
    text = _text(repo_root)
    for flag in flags:
        assert f"(`{flag}`)" in text, f"{RULEBOOK} never asks the person for {flag}"
        assert f"{flag} <" in text, f"{RULEBOOK} never passes {flag} to the setup"


def test_every_file_the_rulebook_names_exists(repo_root):
    named = set(re.findall(r"<framework>/([\w/]+\.(?:py|md|txt))", _text(repo_root)))
    assert TOOL in named
    for path in named:
        assert (repo_root / path).is_file(), f"{RULEBOOK} names {path}, which does not exist"


def test_it_hands_over_to_the_orchestrator(repo_root):
    last = _text(repo_root).split("\n## ")[-1]
    assert "<framework>/agent/run_aspice_agent.md" in last


def test_the_person_keeps_the_decisions(repo_root):
    text = _text(repo_root)
    assert "Never invent a value" in text
    assert "never install, update or remove a plugin yourself" in text
    assert not re.search(r"engram|openspec|\.atl/|gentle-ai", text, re.IGNORECASE)
    assert not re.search(r"git (?:init|submodule)|npx |install_plugins", text)
