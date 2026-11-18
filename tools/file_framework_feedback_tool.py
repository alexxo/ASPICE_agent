"""File a framework feedback entry as an issue of the framework's repository (principle #47).

The product's log, qf.yaml paths.framework_feedback_file, is its own record;
an issue of the framework's repository is the channel that reaches the
framework from any machine (FB-91). This files one entry, written in full from
the log's template, as an issue of the framework's GitHub repository (the URL
.gitmodules records for paths.framework_dir): its title is the entry's, with
the product's repository name to tell where it comes from, its body the full
report. The entry in the log then keeps only the product's part — Date,
Framework version, Status (reported), Issue (the issue's URL), Impact on this
product and Workaround applied — and the team's no-findings lines stay where
they were. An entry that has an Issue is never filed twice.

The issue is public. The developer agent files it only after the person
approved, in the session, the repository, title and body --show prints, and the
publishing. It posts with the person's own GitHub login (gh); opening an issue
of a public repository needs no right on it.

    python tools/file_framework_feedback_tool.py --entry FB-92 --show
    python tools/file_framework_feedback_tool.py --entry FB-92
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.read_commit_range_tool import submodule_url  # noqa: E402
from tools.read_host_tool import HostError, remote_slug, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig, read_product_config  # noqa: E402

FIELDS = ("Date", "Framework version")  # kept as written; Status becomes reported
SECTIONS = ("Impact on this product", "Workaround applied")
_HEAD = re.compile(r"^### (FB-\S+)[ \t]+—[ \t]+(.+)$", re.M)
_NEXT = re.compile(r"^#{1,3} ", re.M)
_FIELD = re.compile(r"^- \*\*(.+?):\*\*")
_SECTION = re.compile(r"^\*\*(.+?)\*\*")
_ACCOUNT = re.compile(r"^(?:- )?\*?No findings for")


@dataclass(frozen=True)
class Filing:
    repository: str  # the framework's, owner/name
    title: str
    body: str  # the full report
    short: str  # what the entry in the log becomes, without its Issue line


def framework_repository(config: ProductConfig) -> str | None:
    """owner/name of the framework's GitHub repository, from .gitmodules."""
    url = submodule_url(config.root, config.relative(config.framework_dir))
    return remote_slug(url) if url else None


def _entry(text: str, name: str) -> tuple[int, int, str] | None:
    """Start, end and summary of the entry name in the log."""
    for head in _HEAD.finditer(text):
        if head.group(1) == name:
            after = _NEXT.search(text, head.end())
            return head.start(), after.start() if after else len(text), head.group(2).strip()
    return None


def _parts(entry: str) -> tuple[dict[str, str], dict[str, str], list[str], list[str]]:
    """The entry's fields and sections by name, its report lines and the
    no-findings lines that sit inside it."""
    fields: dict[str, str] = {}
    sections: dict[str, str] = {}
    report: list[str] = []
    accounts: list[str] = []
    current = None
    for line in entry.splitlines()[1:]:
        if _ACCOUNT.match(line):
            accounts.append(line)
            continue
        report.append(line)
        if found := _FIELD.match(line):
            fields[found.group(1)] = line
            current = None
        elif found := _SECTION.match(line):
            current = found.group(1)
            sections[current] = line
        elif current is not None:
            sections[current] += "\n" + line
    return fields, sections, report, accounts


def prepare(config: ProductConfig, name: str) -> Filing:
    """What filing the entry name would publish, and what it leaves in the log."""
    log = config.framework_feedback_file
    text = log.read_text(encoding="utf-8") if log.is_file() else ""
    found = _entry(text, name)
    if found is None:
        raise ValueError(f"{config.relative(log)} has no entry {name}")
    start, end, summary = found
    fields, sections, report, accounts = _parts(text[start:end])
    if "Issue" in fields:
        url = fields["Issue"].split(":**", 1)[1].strip()
        raise ValueError(f"{name} is filed already: {url}")
    framework = framework_repository(config)
    if framework is None:
        raise ValueError(
            "the framework's repository is not on GitHub: .gitmodules names no GitHub URL "
            f"for {config.relative(config.framework_dir)}"
        )
    missing = [f for f in FIELDS if f not in fields] + [s for s in SECTIONS if s not in sections]
    if missing:
        raise ValueError(f"{name} has no {', '.join(missing)}: complete it from the template")
    product = repository(config.root).split("/")[-1]
    lines = [text[start:end].splitlines()[0], "", *(fields[f] for f in FIELDS)]
    lines += ["- **Status:** reported", ""]
    for section in SECTIONS:
        lines += [sections[section].strip(), ""]
    if accounts:
        lines += [*accounts, ""]
    title = f"{name} ({product}) — {summary}"
    return Filing(framework, title, "\n".join(report).strip() + "\n", "\n".join(lines) + "\n")


def _create(repository: str, title: str, body: str) -> str:
    """Open the issue with the person's GitHub login; its URL."""
    run = subprocess.run(
        ["gh", "issue", "create", "--repo", repository, "--title", title, "--body-file", "-"],
        input=body,
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        raise HostError(run.stderr.strip() or "gh issue create failed")
    return run.stdout.strip().splitlines()[-1]


def file_entry(
    config: ProductConfig, name: str, create: Callable[[str, str, str], str] = _create
) -> str:
    """File the entry name and shorten it in the log; the issue's URL."""
    filing = prepare(config, name)
    url = create(filing.repository, filing.title, filing.body)
    log = config.framework_feedback_file
    text = log.read_text(encoding="utf-8")
    start, end, _ = _entry(text, name)
    short = filing.short.replace(
        "- **Status:** reported", f"- **Status:** reported\n- **Issue:** {url}", 1
    )
    log.write_text(text[:start] + short + text[end:], encoding="utf-8")
    return url


def main(argv: list[str] | None = None, create: Callable[[str, str, str], str] = _create) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--entry", required=True, help="the entry, e.g. FB-92")
    parser.add_argument("--show", action="store_true", help="print what would be published")
    args = parser.parse_args(argv)
    config = read_product_config(args.root)
    try:
        if args.show:
            filing = prepare(config, args.entry)
            print(f"Repository: {filing.repository}\nTitle: {filing.title}\n\n{filing.body}")
            return 0
        print(file_entry(config, args.entry, create))
    except (ValueError, HostError) as problem:
        print(f"Not filed: {problem}.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
