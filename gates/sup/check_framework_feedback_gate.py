"""check_framework_feedback_gate — principle #47: weaknesses logged, framework bumps accounted for.

The framework feedback log, qf.yaml paths.framework_feedback_file, keeps main's
two checks (decision 9 of the quality assurance stage). Every ### FB-<n> entry
under its ## Log heading has every field of the template, a known severity and
class, and no placeholder left (INCOMPLETE_FEEDBACK_ENTRY) — or, once filed as an
issue of the framework's repository by tools/file_framework_feedback_tool.py,
the product's part: Date, Framework version, Status, Issue (a URL of an issue of
the framework's repository), Impact on this product and Workaround applied. An
entry still open or reported has its issue (UNFILED_FEEDBACK_ENTRY). A pull request that
moves the framework submodule (paths.framework_dir) between its base and HEAD
names the new version — its short commit or a release tag on it, as a whole
word — in the log, in the team's own words only: an entry's Framework version
field or a line starting "No findings for". The framework's answers quoted in
the log, and a version named anywhere else, do not account for a bump
(UNACCOUNTED_FRAMEWORK_BUMP).
Whether a weakness was noticed at all is not decidable: an empty log, or none,
passes.

    python gates/sup/check_framework_feedback_gate.py [--root PRODUCT] [--base REF]
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.check_approval_order_tool import in_git  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.file_framework_feedback_tool import framework_repository  # noqa: E402
from tools.read_commit_range_tool import resolve_base  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "check_framework_feedback_gate"
FIELDS = (
    "- **Date:**",
    "- **Framework version:**",
    "- **Severity:**",
    "- **Class:**",
    "- **Status:**",
    "**What the framework claims**",
    "**What actually happens**",
    "**Reproduction**",
    "**Verification**",
    "**Blast radius**",
    "**Impact on this product**",
    "**Workaround applied**",
)
FILED = (  # an entry filed as an issue keeps only the product's part
    "- **Date:**",
    "- **Framework version:**",
    "- **Status:**",
    "- **Issue:**",
    "**Impact on this product**",
    "**Workaround applied**",
)
UNFILED = ("open", "reported")  # statuses whose entry must have its issue
SEVERITIES = ("critical", "high", "medium", "low")
CLASSES = ("C1", "C2", "C3", "C4", "C5", "C6")
PLACEHOLDERS = ("FB-<n>", "YYYY-MM-DD", "<one-line summary>", "<tag> @ <submodule SHA>")
_ENTRY = re.compile(r"^### (FB-\S+)", re.M)
_ACCOUNT = re.compile(r"^(?:- \*\*Framework version:\*\*|(?:- )?\*?No findings for)(.*)$", re.M)


def check(config: ProductConfig, base: str | None = None) -> list[Finding]:
    log = config.framework_feedback_file
    shown = config.relative(log)
    text = log.read_text(encoding="utf-8") if log.is_file() else ""
    start, body = _log_section(text)
    findings = [
        Finding(rule, shown, line, f"{entry}: {problem}")
        for rule, entry, line, problem in _problems(body, start, framework_repository(config))
    ]
    if in_git(config.root):
        bump = _bump(config, base)
        if bump is not None and not _accounted(body, bump):
            findings.append(
                Finding(
                    "UNACCOUNTED_FRAMEWORK_BUMP",
                    shown,
                    None,
                    f"The framework moved to {' / '.join(sorted(bump))} in this pull request, "
                    "but no entry's Framework version or no-findings line under ## Log names "
                    "it; record what you found, or a line such as "
                    f"'No findings for {sorted(bump)[-1]}'.",
                )
            )
    return findings


def _log_section(text: str) -> tuple[int, str]:
    """The text under ## Log, and the line it starts after (0: the whole file)."""
    found = re.search(r"^## Log[ \t]*$", text, re.M)
    if not found:
        return 0, text
    return text[: found.end()].count("\n"), text[found.end() :]


def _accounted(body: str, bump: set[str]) -> bool:
    """Whether the team's own words name the new version: an entry's Framework
    version field or a no-findings line, never a quoted answer or other prose."""
    said = " ".join(found.group(1) for found in _ACCOUNT.finditer(body))
    return any(re.search(rf"(?<![\w.]){re.escape(name)}(?!\w|\.\w)", said) for name in bump)


def _problems(body: str, start: int, framework: str | None) -> list[tuple[str, str, int, str]]:
    """(rule, entry, line, problem) for every entry; framework is the framework's
    repository, owner/name, when .gitmodules names it on GitHub."""
    incomplete = "INCOMPLETE_FEEDBACK_ENTRY"
    problems = []
    heads = list(_ENTRY.finditer(body))
    for i, head in enumerate(heads):
        entry = body[head.start() : heads[i + 1].start() if i + 1 < len(heads) else len(body)]
        line = start + body[: head.start()].count("\n") + 1
        name = head.group(1)
        issue = _value(entry, "Issue")
        for field in FILED if issue is not None else FIELDS:
            if field not in entry:
                problems.append(
                    (incomplete, name, line, f"missing '{field}' (write n/a, never omit it)")
                )
        for placeholder in PLACEHOLDERS:
            if placeholder in entry:
                problems.append(
                    (incomplete, name, line, f"still has the template's '{placeholder}'")
                )
        for field, allowed in (("Severity", SEVERITIES), ("Class", CLASSES)):
            value = _value(entry, field)
            if value is not None and value not in allowed:
                problems.append(
                    (
                        incomplete,
                        name,
                        line,
                        f"{field.lower()} '{value}' is not one of {', '.join(allowed)}",
                    )
                )
        repo = re.escape(framework) if framework else r"[\w.-]+/[\w.-]+"
        if issue is not None and not re.fullmatch(rf"https://github\.com/{repo}/issues/\d+", issue):
            where = framework or "the framework's repository"
            problems.append((incomplete, name, line, f"Issue '{issue}' is no issue of {where}"))
        status = _value(entry, "Status") or ""
        if issue is None and status.split(" ")[0] in UNFILED:
            problems.append(
                (
                    "UNFILED_FEEDBACK_ENTRY",
                    name,
                    line,
                    f"it is {status} but not filed as an issue of the framework's repository, so "
                    f"the framework never sees it; once the person approved it, run "
                    f"tools/file_framework_feedback_tool.py --entry {name}",
                )
            )
    return problems


def _value(entry: str, field: str) -> str | None:
    found = re.search(rf"^- \*\*{field}:\*\*[ \t]*(.*)$", entry, re.M)
    return found.group(1).strip() if found else None


def _git(root: Path, *args: str) -> str | None:
    run = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else None


def _pin(root: Path, rev: str, path: str) -> str | None:
    entry = _git(root, "ls-tree", rev, "--", path) or ""
    mode, _, rest = entry.partition(" ")
    return rest.split()[1] if mode == "160000" else None


def _bump(config: ProductConfig, base: str | None) -> set[str] | None:
    """The names of the new framework version, when the range moved the submodule."""
    base_sha = resolve_base(config.root, base)
    if base_sha is None:
        return None
    path = config.relative(config.framework_dir)
    new = _pin(config.root, "HEAD", path)
    if new is None or new == _pin(config.root, base_sha, path):
        return None
    tags = _git(config.framework_dir, "tag", "--points-at", new) or ""
    return {new[:7], *tags.split()}


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
