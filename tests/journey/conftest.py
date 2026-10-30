"""Scenarios run on a copy of the example product, as the agent would find it."""

import shutil

import pytest
from product_builder import approve_checkpoint, commit_all


@pytest.fixture
def product(repo_root, tmp_path, isolated_home):
    """The example product, with its plugins installed on the machine by hand.

    Plugins are tools on the person's machine (~/.agents/skills), not part of
    the product: the example-method stand-ins are copied there, and a stand-in
    takes Archify's place, since this stage never runs it.
    """
    root = tmp_path / "login-product"
    shutil.copytree(repo_root / "examples" / "login-product", root)
    skills = isolated_home / ".agents" / "skills"
    for name in ("design", "apply", "verify"):
        shutil.copytree(repo_root / "examples/example-method/skills" / name, skills / name)
    standin = skills / "archify" / "SKILL.md"
    standin.parent.mkdir(parents=True)
    standin.write_text("---\nname: archify\ndescription: stand-in for the test\n---\n")
    commit_all(root, "example product at the start of SWE.1")  # the approval gate needs history
    approve_checkpoint(root, 1)  # the architect approved the diagrams on the host
    return root
