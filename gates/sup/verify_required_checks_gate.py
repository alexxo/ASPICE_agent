"""verify_required_checks_gate — SUP.1 BP1, BP6: no gate can be switched off.

The product's CI file (qf.yaml paths.ci_file) has a job that runs the gates of
every stage reached (resolve_stage_tool.py --check). The default branch is
protected, read from the host (decision 6 of the quality assurance stage):
changes arrive through reviewed pull requests (BRANCH_NOT_PROTECTED); that job
is a required check, so no merge happens with a red gate (CHECK_NOT_REQUIRED);
code owners must approve, and admins cannot bypass any of it
(PROTECTION_BYPASSABLE). CODEOWNERS names an owner for the CI file, the
framework submodule (.gitmodules) and the architecture folder (UNOWNED_PATH),
so none changes without a person's approval.

    python gates/sup/verify_required_checks_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import fnmatch
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_host_tool import read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "verify_required_checks_gate"
CODEOWNERS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")
GATES_COMMAND = "resolve_stage_tool.py"


def check(config: ProductConfig) -> list[Finding]:
    ci = config.relative(config.ci_file)
    findings = []
    job = gates_job(config.ci_file)
    if job is None:
        findings.append(
            Finding(
                "CHECK_NOT_REQUIRED",
                ci,
                None,
                f"The CI file has no job that runs {GATES_COMMAND} --check, so the gates "
                "never run on a pull request; start from templates/github/quality_gates.yml.",
            )
        )
    host = read_host()
    repo = repository(config.root)
    branch = host.default_branch(repo)
    protection = host.protection(repo, branch)
    if protection is None or not protection.reviews_required:
        findings.append(
            Finding(
                "BRANCH_NOT_PROTECTED",
                ci,
                None,
                f"Branch {branch} of {repo} does not require a reviewed pull request; "
                "protect it so every change arrives as a delivery.",
            )
        )
    else:
        if job is not None and job not in protection.required_checks:
            findings.append(
                Finding(
                    "CHECK_NOT_REQUIRED",
                    ci,
                    None,
                    f"Job '{job}' runs the gates but is not a required check of {branch}; "
                    "a pull request could merge with a red gate.",
                )
            )
        if not (protection.code_owner_reviews and protection.enforce_admins):
            missing = [
                name
                for name, on in (
                    ("code-owner review", protection.code_owner_reviews),
                    ("enforcement for admins", protection.enforce_admins),
                )
                if not on
            ]
            findings.append(
                Finding(
                    "PROTECTION_BYPASSABLE",
                    ci,
                    None,
                    f"Branch {branch} lacks {' and '.join(missing)}; the gates and their "
                    "files could be changed without a person's approval.",
                )
            )
    owners, file = codeowners(config.root)
    architecture = config.relative(config.architecture_dir).rstrip("/")
    for path, what in (
        (ci, "the CI file"),
        (".gitmodules", "the framework pin"),
        (f"{architecture}/", "the architecture"),
    ):
        if not owned(owners, path):
            findings.append(
                Finding(
                    "UNOWNED_PATH",
                    file or CODEOWNERS[0],
                    None,
                    f"No code owner for {what} ({path}); add a CODEOWNERS line naming a "
                    "person, so a change to it needs their approval.",
                )
            )
    return findings


def gates_job(ci_file: Path) -> str | None:
    """The name of the CI job that runs the gates — the check branch protection requires."""
    try:
        workflow = read_yaml_file(ci_file) if ci_file.is_file() else None
    except YamlReadError:
        return None
    jobs = (workflow or {}).get("jobs") or {}
    for key, job in jobs.items() if isinstance(jobs, dict) else ():
        for step in (job or {}).get("steps") or ():
            run = str((step or {}).get("run", ""))
            if GATES_COMMAND in run and "--check" in run:
                return str(job.get("name", key))
    return None


def codeowners(root: Path) -> tuple[list[tuple[str, list[str]]], str | None]:
    """The CODEOWNERS rules as (pattern, owners), and the file they came from."""
    for name in CODEOWNERS:
        path = root / name
        if path.is_file():
            rules = []
            for line in path.read_text().splitlines():
                parts = line.split("#", 1)[0].split()
                if parts:
                    rules.append((parts[0], parts[1:]))
            return rules, name
    return [], None


def owned(rules: list[tuple[str, list[str]]], path: str) -> bool:
    """The last matching rule names an owner (GitHub: the last match wins)."""
    owners: list[str] = []
    for pattern, names in rules:
        if _matches(pattern, path):
            owners = names
    return bool(owners)


def _matches(pattern: str, path: str) -> bool:
    directory = path.endswith("/")
    target = path.rstrip("/")
    body = pattern.strip("/")
    anchored = pattern.startswith("/") or "/" in body  # as in .gitignore
    if pattern.rstrip("/") in ("*", "**", ""):
        return True
    segments = target.split("/")
    # A pattern matches the path itself or any folder above it.
    candidates = ["/".join(segments[: i + 1]) for i in range(len(segments))]
    for i, candidate in enumerate(candidates):
        if pattern.endswith("/") and i == len(candidates) - 1 and not directory:
            continue  # a folder pattern never matches the file itself
        tails = (
            [candidate]
            if anchored
            else ["/".join(candidate.split("/")[j:]) for j in range(candidate.count("/") + 1)]
        )
        if any(fnmatch.fnmatchcase(t, body) for t in tails):
            return True
    return False


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
