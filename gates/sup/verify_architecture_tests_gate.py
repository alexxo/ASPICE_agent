"""verify_architecture_tests_gate — principle #4, SWE.2 BP5: an architecture PR holds no code.

A pull request that changes qf.yaml paths.architecture_dir changes nothing under
paths.code_dir (CODE_IN_ARCHITECTURE_PR): the architecture is agreed before any
code is built on it, so its review is about the plan alone. The pull request is
base..HEAD, as for every history gate; check_track_rule_gate keeps the rest of
the feature track out.

    python gates/sup/verify_architecture_tests_gate.py [--root PRODUCT] [--base REF]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gates.sup.check_track_rule_gate import architecture_paths, changed_paths, under  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "verify_architecture_tests_gate"


def check(config: ProductConfig, base: str | None = None) -> list[Finding]:
    paths = changed_paths(config, base)
    architecture = architecture_paths(config, paths)
    code = [p for p in paths if under(config, p, config.code_dir)]
    if not (architecture and code):
        return []
    return [
        Finding(
            "CODE_IN_ARCHITECTURE_PR",
            path,
            None,
            f"{path} is code in a pull request that changes the architecture "
            f"({architecture[0]}); the code comes in a feature pull request once the "
            "architecture is merged.",
        )
        for path in code
    ]


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
