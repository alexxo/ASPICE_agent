"""gates/sup/check_framework_feedback_gate.py — weaknesses logged, version bumps accounted for."""

import subprocess

import pytest
from product_builder import add_framework, build_product, commit_all, git_head, make_framework

from gates.sup.check_framework_feedback_gate import check
from tools.read_product_config_tool import read_product_config

LOG = "FRAMEWORK_FEEDBACK.md"
ENTRY = """\
### FB-1 — the glossary gate passes an empty glossary

- **Date:** 2026-10-11
- **Framework version:** v6.0.0 @ 1a2b3c4
- **Severity:** critical
- **Class:** C1
- **Status:** reported

**What the framework claims** — docs, § 4.1 SWE.1 BP1.

**What actually happens** — `check_glossary_gate` exits 0 on an empty file.

**Reproduction** — an empty docs/glossary.md.

**Verification** — run.

**Blast radius** — every product.

**Impact on this product** — none; caught by the reviewer.

**Workaround applied** — none.
"""


def _log(root, *entries):
    (root / LOG).write_text("# Framework feedback\n\n## Log\n\n" + "\n".join(entries))


@pytest.fixture
def product(tmp_path):
    root = build_product(tmp_path / "product")
    subprocess.run(["git", "-C", str(root), "branch", "-M", "main"], check=True)
    return root


def _rules(root, base=None):
    return sorted(f.rule for f in check(read_product_config(root), base=base))


def test_no_log_or_an_empty_one_passes(product):
    assert _rules(product) == []
    _log(product)
    assert _rules(product) == []


def test_a_complete_entry_passes(product):
    _log(product, ENTRY)
    assert _rules(product) == []


@pytest.mark.parametrize(
    "broken",
    [
        ENTRY.replace("- **Severity:** critical\n", ""),
        ENTRY.replace("**Blast radius** — every product.\n", ""),
        ENTRY.replace("critical", "urgent"),
        ENTRY.replace("- **Class:** C1", "- **Class:** C9"),
        ENTRY.replace("2026-10-11", "YYYY-MM-DD"),
    ],
)
def test_an_incomplete_entry_is_caught(product, broken):
    _log(product, broken)
    (finding,) = check(read_product_config(product))
    assert (finding.rule, finding.line) == ("INCOMPLETE_FEEDBACK_ENTRY", 5)


def test_the_template_above_the_log_is_not_an_entry(product):
    template = "## Entry template\n\n### FB-<n> — <one-line summary>\n\n"
    (product / LOG).write_text(f"# Framework feedback\n\n{template}## Log\n")
    assert _rules(product) == []


@pytest.fixture
def bumped(tmp_path):
    framework = tmp_path / "framework"
    make_framework(framework)
    root = build_product(tmp_path / "bumped")
    add_framework(root, framework)
    subprocess.run(["git", "-C", str(root), "branch", "-M", "main"], check=True)
    subprocess.run(["git", "-C", str(root), "checkout", "-q", "-b", "feature/bump"], check=True)
    (framework / "NEW.md").write_text("a new gate\n")
    commit_all(framework, "new gate")
    subprocess.run(["git", "-C", str(framework), "tag", "v6.1.0"], check=True)
    fw = root / ".framework"
    subprocess.run(["git", "-C", str(fw), "fetch", "-q", "--tags", "origin"], check=True)
    subprocess.run(["git", "-C", str(fw), "checkout", "-q", "v6.1.0"], check=True)
    commit_all(root, "bump the framework")
    return root, git_head(framework)


def test_a_silent_framework_bump_is_caught(bumped):
    root, _ = bumped
    assert _rules(root, base="main") == ["UNACCOUNTED_FRAMEWORK_BUMP"]


@pytest.mark.parametrize(
    "line",
    [
        "- No findings for v6.1.0",
        "- No findings for {short}",
        "*No findings for v6.1.0 ({short}).*",
        ENTRY.replace("v6.0.0 @ 1a2b3c4", "v6.1.0 @ {short}"),
    ],
)
def test_a_bump_named_in_the_log_is_accounted_for(bumped, line):
    root, sha = bumped
    _log(root, line.format(short=sha[:7]) + "\n")
    assert _rules(root, base="main") == []


@pytest.mark.parametrize(
    "line",
    [
        "> **Framework response, 2026-10-23 — FB-1, resolved in v6.1.0 ({short}).**",
        ENTRY.replace("- **Status:** reported", "- **Status:** fixed upstream in v6.1.0"),
        "- No findings for v6.1.0.1",
        "- No findings for x{short}",
    ],
)
def test_a_version_named_elsewhere_does_not_account_for_a_bump(bumped, line):
    """A quoted answer, another field, a longer version: none is the team's account."""
    root, sha = bumped
    _log(root, line.format(short=sha[:7]) + "\n")
    assert _rules(root, base="main") == ["UNACCOUNTED_FRAMEWORK_BUMP"]


def test_without_a_bump_the_log_need_not_name_a_version(bumped):
    root, _ = bumped
    assert _rules(root, base="HEAD") == []
