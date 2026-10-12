"""Shared fixtures for the framework's self-tests.

Every path resolves from the root of this tree (the parent of
tests/), never from wherever pytest was started, so the suite runs
the same from any directory — and from a copy of the tree on its own.
The root is also put on the import path, so tests import the framework's
code as `tools.<name>`, `gates.swe.<name>`, `adapters.<name>`.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
for path in (ROOT, TESTS):  # framework code, and test helpers such as product_builder
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def product(tmp_path):
    """A complete product that passes every SWE.1 gate; see product_builder."""
    from product_builder import build_product

    return build_product(tmp_path)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path_factory, monkeypatch):
    """Every test runs with an empty home directory, so plugins installed on the
    machine running the tests (~/.agents/skills, ~/.claude/skills) are never seen."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    return home


HOST_VARIABLES = (
    "QF_HOST_TOKEN",
    "QF_HOST_FILE",
    "GITHUB_REPOSITORY",
    "GITHUB_EVENT_PATH",
    "GITHUB_REF_NAME",
    "GITHUB_API_URL",
)


@pytest.fixture(autouse=True)
def no_real_host(monkeypatch):
    """No test reads a real code host: the framework's own CI sets GITHUB_* for
    its own repository, and a developer's token must never be used."""
    for name in HOST_VARIABLES:
        monkeypatch.delenv(name, raising=False)
