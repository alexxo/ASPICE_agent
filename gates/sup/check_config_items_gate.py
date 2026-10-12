"""check_config_items_gate — SUP.8 BP1: every configuration item under version control.

The configuration items are qf.yaml and every path it declares — the framework
pin included — plus the product's own (qf.yaml config_items); the release
records are the baselines, not items (decision 4 of the configuration
management stage). Each item exists (MISSING_CONFIG_ITEM; an empty folder is
missing, git cannot hold it) and is tracked by git:
not ignored, with no file in it left untracked (UNTRACKED_CONFIG_ITEM). The
scenarios folder is the one item written after this stage (stage 11): it is
required once it exists, and verify_acceptance_to_wishes_link_gate requires
the scenarios themselves (decision 15 of the validation stage).

    python gates/sup/check_config_items_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.check_approval_order_tool import in_git  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.write_release_tool import config_items  # noqa: E402

GATE = "check_config_items_gate"


def check(config: ProductConfig) -> list[Finding]:
    root = config.root
    if not in_git(root):
        return [
            Finding(
                "NOT_A_GIT_REPOSITORY",
                ".",
                None,
                "The product is not a git repository, so nothing is under version control.",
            )
        ]
    later = config.relative(config.validation_scenarios_dir)
    findings = []
    for item in config_items(config):
        path = root / item
        if item == later and not path.exists():
            continue
        if not path.exists() or (path.is_dir() and not any(path.iterdir())):
            findings.append(
                Finding(
                    "MISSING_CONFIG_ITEM",
                    item,
                    None,
                    f"Configuration item {item} does not exist; create it, or remove it from "
                    "qf.yaml if it is the product's own.",
                )
            )
            continue
        why = _untracked(root, item)
        if why:
            findings.append(Finding("UNTRACKED_CONFIG_ITEM", item, None, why))
    return findings


def _untracked(root: Path, item: str) -> str | None:
    if _git(root, "check-ignore", "-q", "--no-index", item).returncode == 0:
        return f"Configuration item {item} is ignored by git; remove it from .gitignore."
    if not _git(root, "ls-files", "--", item).stdout.strip():
        return f"Configuration item {item} is not tracked by git; add and commit it."
    others = _git(root, "ls-files", "--others", "--exclude-standard", "--", item).stdout.split()
    if others:
        return f"{others[0]} in configuration item {item} is not tracked by git; commit it."
    return None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
