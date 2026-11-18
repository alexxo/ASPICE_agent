"""tools/file_framework_feedback_tool.py — an entry reaches the framework as its issue (FB-91)."""

import subprocess

import pytest
from product_builder import FRAMEWORK_REPO, add_origin, build_product

from gates.sup.check_framework_feedback_gate import check
from tools import file_framework_feedback_tool as tool
from tools.read_product_config_tool import read_product_config

LOG = "FRAMEWORK_FEEDBACK.md"
OLDER = """\
### FB-1 — an older finding

- **Date:** 2026-10-11
- **Framework version:** v6.0.0 @ 1a2b3c4
- **Severity:** low
- **Class:** C6
- **Status:** fixed upstream in v6.0.1

**What the framework claims** — a.

**What actually happens** — b.

**Reproduction** — c.

**Verification** — run.

**Blast radius** — every product.

**Impact on this product** — none.

**Workaround applied** — none.
"""
ENTRY = """\
### FB-2 — the glossary gate passes an empty glossary

- **Date:** 2026-11-18
- **Framework version:** v6.1.0 @ 5d6e7f8
- **Severity:** critical
- **Class:** C1
- **Status:** open

**What the framework claims** — docs, § 4.1 SWE.1 BP1.

**What actually happens** — `check_glossary_gate` exits 0 on an empty file:
the run printed `pass`.

**Reproduction** — an empty docs/glossary.md.

**Verification** — run.

**Blast radius** — every product.

**Impact on this product** — the glossary was never checked;
caught by the reviewer.

**Workaround applied** — none.

No findings for v6.1.0 (5d6e7f8).

"""
URL = f"https://github.com/{FRAMEWORK_REPO}/issues/31"


@pytest.fixture
def product(tmp_path):
    root = build_product(tmp_path / "product")
    add_origin(root)
    modules = ["git", "config", "-f", str(root / ".gitmodules")]
    subprocess.run([*modules, "submodule.framework.path", ".framework"], check=True)
    url = f"https://github.com/{FRAMEWORK_REPO}.git"
    subprocess.run([*modules, "submodule.framework.url", url], check=True)
    (root / LOG).write_text("# Framework feedback\n\n## Log\n\n" + ENTRY + OLDER)
    return root


def _filed(created):
    def create(repository, title, body):
        created.append((repository, title, body))
        return URL

    return create


def test_show_prints_what_would_be_published_and_files_nothing(product, capsys):
    before = (product / LOG).read_text()
    assert tool.main(["--root", str(product), "--entry", "FB-2", "--show"], _filed([])) == 0
    out = capsys.readouterr().out
    assert f"Repository: {FRAMEWORK_REPO}" in out
    assert "Title: FB-2 (login) — the glossary gate passes an empty glossary" in out
    assert "**What actually happens**" in out and "No findings for" not in out
    assert (product / LOG).read_text() == before


def test_filing_publishes_the_report_and_keeps_the_products_part(product, capsys):
    created = []
    assert tool.main(["--root", str(product), "--entry", "FB-2"], _filed(created)) == 0
    assert capsys.readouterr().out.strip() == URL
    ((repository, title, body),) = created
    assert (repository, title) == (
        FRAMEWORK_REPO,
        "FB-2 (login) — the glossary gate passes an empty glossary",
    )
    assert body.startswith("- **Date:** 2026-11-18") and "the run printed `pass`." in body
    log = (product / LOG).read_text()
    assert log == (
        "# Framework feedback\n\n## Log\n\n"
        "### FB-2 — the glossary gate passes an empty glossary\n\n"
        "- **Date:** 2026-11-18\n"
        "- **Framework version:** v6.1.0 @ 5d6e7f8\n"
        "- **Status:** reported\n"
        f"- **Issue:** {URL}\n\n"
        "**Impact on this product** — the glossary was never checked;\n"
        "caught by the reviewer.\n\n"
        "**Workaround applied** — none.\n\n"
        "No findings for v6.1.0 (5d6e7f8).\n\n" + OLDER
    )
    assert check(read_product_config(product)) == []


def test_an_entry_is_never_filed_twice(product, capsys):
    tool.main(["--root", str(product), "--entry", "FB-2"], _filed([]))
    created = []
    assert tool.main(["--root", str(product), "--entry", "FB-2"], _filed(created)) == 2
    assert created == [] and f"filed already: {URL}" in capsys.readouterr().err


def test_without_the_framework_on_github_nothing_is_filed(product, capsys):
    (product / ".gitmodules").unlink()
    created = []
    assert tool.main(["--root", str(product), "--entry", "FB-2"], _filed(created)) == 2
    assert created == [] and "not on GitHub" in capsys.readouterr().err
