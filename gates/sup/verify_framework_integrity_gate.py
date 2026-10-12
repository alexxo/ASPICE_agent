"""verify_framework_integrity_gate — SUP.1 BP1, BP2: the framework pinned, untouched and released.

The framework lives in the product as a git submodule at qf.yaml
paths.framework_dir, so the version a product runs changes only through its own
pull request (decision 5 of the quality assurance stage). The submodule is
declared in .gitmodules and pinned in the commit (FRAMEWORK_NOT_PINNED); its
checkout is at the pinned commit with no local change (FRAMEWORK_MODIFIED); and
the pinned commit is tagged as a release of the framework's repository, read
from the host (FRAMEWORK_NOT_RELEASED).

    python gates/sup/verify_framework_integrity_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.check_approval_order_tool import in_git  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_commit_range_tool import GITMODULES, gitlink, submodule_url  # noqa: E402
from tools.read_host_tool import read_host, remote_slug  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "verify_framework_integrity_gate"


def check(config: ProductConfig) -> list[Finding]:
    if not in_git(config.root):
        return [
            Finding(
                "NOT_A_GIT_REPOSITORY",
                ".",
                None,
                "The product is not a git repository, so the framework cannot be pinned.",
            )
        ]
    path = config.relative(config.framework_dir)
    pinned = gitlink(config.root, "HEAD", path)
    url = submodule_url(config.root, path)
    if pinned is None or url is None:
        return [
            Finding(
                "FRAMEWORK_NOT_PINNED",
                GITMODULES,
                None,
                f"{path} is not a git submodule pinned in the last commit; add the framework "
                f"with git submodule add <framework repository> {path} and commit it.",
            )
        ]
    findings = []
    checked_out = _git(config.framework_dir, "rev-parse", "HEAD")
    if not (config.framework_dir / ".git").exists() or checked_out != pinned:
        findings.append(
            Finding(
                "FRAMEWORK_MODIFIED",
                path,
                None,
                f"The framework is pinned at {pinned[:7]} but checked out at "
                f"{(checked_out or 'nothing')[:7]}; run git submodule update {path}.",
            )
        )
    else:
        changed = _git(config.framework_dir, "status", "--porcelain")
        if changed:
            first = changed.splitlines()[0][3:]
            findings.append(
                Finding(
                    "FRAMEWORK_MODIFIED",
                    path,
                    None,
                    f"The framework's checkout has local changes (e.g. {first}); the gates "
                    "must run as released — record the weakness in the framework feedback "
                    "log instead.",
                )
            )
    slug = remote_slug(url)
    if slug is None or pinned not in read_host().release_tags(slug).values():
        findings.append(
            Finding(
                "FRAMEWORK_NOT_RELEASED",
                GITMODULES,
                None,
                f"The pinned commit {pinned[:7]} is not a tagged release of {slug or url}; "
                "pin a released framework version.",
            )
        )
    return findings


def _git(root: Path, *args: str) -> str | None:
    run = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else None


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
