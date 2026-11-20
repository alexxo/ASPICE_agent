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


def test_the_first_commit_passes_the_gates_of_its_pull_request(repo_root):
    """FB-1, FB-2 of TBO-STUDIO: the prescribed message named no issue, and no
    step accounted for the release the first commit pins."""
    from gates.sup.check_commit_conventions_gate import CONVENTIONAL, TOKEN
    from gates.sup.check_framework_feedback_gate import _accounted

    text = " ".join(_text(repo_root).split())
    filled = {"<release>": "v5.4.4", "<commit>": "a1b2c3d", "<n>": "2"}
    (message,) = re.findall(r"`(chore: start the product[^`]*)`", text)
    (line,) = re.findall(r"\*(No findings for <release> \(<commit>\))\*", text)
    for name, value in filled.items():
        message, line = message.replace(name, value), line.replace(name, value)
    assert CONVENTIONAL.match(message) and TOKEN.search(message), message
    assert _accounted(f"\n{line}\n", {"v5.4.4", "a1b2c3d"}), line
