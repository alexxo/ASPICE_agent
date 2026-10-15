"""verify_history_kept_gate — SUP.8 BP3, BP4: the main branch's history is never rewritten.

On every push to the main branch, the main branch before the push is still in
its history after it (MAIN_REWRITTEN): a force-push that drops commits is
caught on the push itself, and the lost commits come back from any clone that
still has them. No host setting is read (decision 7 of the configuration
management stage); the rulebooks forbid the agent to rewrite the main branch.
Outside a push to the main branch there is nothing to compare.

    python gates/sup/verify_history_kept_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_commit_range_tool import is_ancestor, main_push  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "verify_history_kept_gate"


def check(config: ProductConfig) -> list[Finding]:
    push = main_push()
    if push is None or push.before is None:
        return []
    if is_ancestor(config.root, push.before, push.after or "HEAD"):
        return []
    lost = push.before[:7]
    return [
        Finding(
            "MAIN_REWRITTEN",
            ".",
            None,
            f"This push dropped the main branch's previous state {lost} from its history: "
            f"a force-push rewrote it. Bring the lost commits back from a clone that has "
            f"{lost} (e.g. git merge {lost}) — never with another force-push.",
        )
    ]


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
