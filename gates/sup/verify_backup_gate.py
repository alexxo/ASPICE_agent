"""verify_backup_gate — SUP.8 BP8: every release is in the mirror.

The product declares a second repository that mirrors it (qf.yaml mirror). Every
release tag is present there, pointing at the same tag object
(TAG_NOT_IN_MIRROR): the backup holds every baseline and can be fetched from.
A mirror that cannot be reached raises MirrorError, which crashes the gate: the
runner fails closed. Without a release there is nothing to check. A full restore
of the host is left to the organisation's recovery procedure.

    python gates/sup/verify_backup_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.write_release_tool import release_tags  # noqa: E402

GATE = "verify_backup_gate"


class MirrorError(Exception):
    """The mirror cannot be read."""


def check(config: ProductConfig) -> list[Finding]:
    tags = release_tags(config.root)
    if not tags:
        return []
    mirrored = _mirror_tags(config.root, config.mirror)
    findings = []
    for tag in tags:
        local = _git(config.root, "rev-parse", f"refs/tags/{tag}").stdout.strip()
        if mirrored.get(tag) != local:
            findings.append(
                Finding(
                    "TAG_NOT_IN_MIRROR",
                    ".",
                    None,
                    f"Release tag {tag} is not in the mirror {config.mirror}"
                    + (" as released" if tag in mirrored else "")
                    + "; push it there, or repair the mirroring.",
                )
            )
    return findings


def _mirror_tags(root: Path, mirror: str) -> dict[str, str]:
    run = _git(root, "ls-remote", "--tags", mirror)
    if run.returncode != 0:
        raise MirrorError(f"The mirror {mirror} cannot be read: {run.stderr.strip()}")
    tags = {}
    for line in run.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.startswith("refs/tags/") and not ref.endswith("^{}"):
            tags[ref[len("refs/tags/") :]] = sha
    return tags


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
