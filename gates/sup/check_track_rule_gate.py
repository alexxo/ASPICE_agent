"""check_track_rule_gate — SWE.2 BP5, SUP.8 BP3: the architecture travels on its own track.

A pull request that changes qf.yaml paths.architecture_dir is an architecture
pull request (as for the person's sample, verify_delivery_reviewed_gate). It changes
no feature-track work product — the detailed design, the verification plan, the
environment variables, the integration and software tests, the observability
definitions (MIXED_TRACKS) — and comes from an arch/<slug> branch
(ARCHITECTURE_OFF_BRANCH). The code is verify_architecture_tests_gate's. The
pull request is base..HEAD, as for every history gate.

    python gates/sup/check_track_rule_gate.py [--root PRODUCT] [--base REF]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_commit_range_tool import branch, commits, resolve_base  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "check_track_rule_gate"
ARCH_PREFIX = "arch/"


def changed_paths(config: ProductConfig, base: str | None) -> list[str]:
    """Every path the pull request's commits change, in order of first change."""
    paths: dict[str, None] = {}
    for commit in commits(config.root, resolve_base(config.root, base)):
        for change in commit.changes:
            paths.setdefault(change.path)
    return list(paths)


def under(config: ProductConfig, path: str, target: Path) -> bool:
    item = config.relative(target).rstrip("/")
    return path == item or path.startswith(item + "/")


def architecture_paths(config: ProductConfig, paths: list[str]) -> list[str]:
    return [p for p in paths if under(config, p, config.architecture_dir)]


def check(config: ProductConfig, base: str | None = None) -> list[Finding]:
    paths = changed_paths(config, base)
    architecture = architecture_paths(config, paths)
    if not architecture:
        return []
    feature = (
        config.detailed_design_dir,
        config.verification_plan_file,
        config.env_variables_file,
        config.integration_tests_dir,
        config.software_tests_dir,
        config.observability_dir,
    )
    mixed = [p for p in paths if any(under(config, p, f) for f in feature)]
    findings = []
    if mixed:
        findings.append(
            Finding(
                "MIXED_TRACKS",
                mixed[0],
                None,
                f"This pull request changes the architecture ({architecture[0]}) and the "
                f"feature track ({', '.join(mixed[:3])}); split it, architecture first.",
            )
        )
    name = branch(config.root)
    if not (name or "").startswith(ARCH_PREFIX):
        findings.append(
            Finding(
                "ARCHITECTURE_OFF_BRANCH",
                architecture[0],
                None,
                f"The architecture changes on branch '{name or 'detached'}'; move them to an "
                "arch/<slug> branch and their own pull request.",
            )
        )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
