"""Run gates on a product and collect their results.

Each gate runs as its own command, exactly as CI runs it, and its findings.v1
output is collected. A gate that does not exist, crashes, or prints something
that is not findings.v1 is a failed gate (GATE_MISSING, GATE_CRASHED): the
runner fails closed, never open.

    python agent/run_gates_tool.py [--root PRODUCT] (--stage ID | --all)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.read_stages_tool import Stage, UnknownStage, read_stages, stage  # noqa: E402
from agent.record_checkpoint_tool import current_approval  # noqa: E402
from tools.emit_findings_tool import Finding, result  # noqa: E402
from tools.read_product_config_tool import ConfigError, read_product_config  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

__all__ = ["GATES_DIR", "passed", "reached_gates", "run_gates"]

GATES_DIR = Path(__file__).resolve().parent.parent / "gates"


def run_gates(root: Path, gates: Sequence[str]) -> list[dict]:
    """One findings.v1 document per gate, in the given order."""
    return [_run(Path(root), gate) for gate in gates]


def reached_gates(root: Path, s: Stage) -> tuple[str, ...]:
    """The stage's gates, plus those after its checkpoint once that is approved."""
    if not s.gates_after_checkpoint:
        return s.gates
    try:
        config = read_product_config(Path(root))
    except ConfigError:
        return s.gates
    approval, _why = current_approval(config, s.checkpoint, s.approves)
    return s.built_gates if approval is not None else s.gates


def passed(results: list[dict]) -> bool:
    return all(r["result"] == "pass" for r in results)


def _run(root: Path, gate: str) -> dict:
    scripts = sorted(GATES_DIR.glob(f"*/{gate}.py"))
    if not scripts:
        return result(
            gate,
            [
                Finding(
                    "GATE_MISSING", "agent/stages.yaml", None, f"Gate {gate} is not implemented."
                )
            ],
        )
    run = subprocess.run(
        [sys.executable, str(scripts[0]), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        doc = json.loads(run.stdout)
    except json.JSONDecodeError:
        doc = None
    if run.returncode not in (0, 1) or doc is None or validate(doc, "findings"):
        detail = (run.stderr.strip().splitlines() or ["no output"])[-1]
        return result(
            gate,
            [
                Finding(
                    "GATE_CRASHED",
                    f"gates/{scripts[0].parent.name}/{scripts[0].name}",
                    None,
                    f"Gate exited {run.returncode} without a valid result: {detail}",
                )
            ],
        )
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--stage", help="run the gates the stage has reached")
    which.add_argument("--all", action="store_true", help="run every implemented gate")
    args = parser.parse_args(argv)
    if args.all:
        gates = [g for s in read_stages() if s.implemented for g in s.built_gates]
    else:
        try:
            chosen = stage(args.stage)
        except UnknownStage as err:
            print(str(err), file=sys.stderr)
            return 2
        gates = list(reached_gates(args.root, chosen))
    results = run_gates(args.root, gates)
    print(json.dumps({"result": "pass" if passed(results) else "fail", "gates": results}, indent=2))
    return 0 if passed(results) else 1


if __name__ == "__main__":
    sys.exit(main())
