"""Run a gate as a command: the same interface for every gate.

    python gates/<group>/<gate>.py [--root PRODUCT] [--base REF]

The gate's check receives the product configuration and returns its findings.
A gate that reads the pull request's commits also takes base, the reference the
range starts after (decision 9); without --base it comes from QF_BASE or the
main branch.
The result is printed in findings.v1. Exit codes: 0 pass, 1 fail — a missing or
invalid qf.yaml is a finding too, and so is a code host that cannot be read
(HOST_UNREADABLE), so the gate fails closed —, 2 wrong usage.
"""

from __future__ import annotations

import argparse
import inspect
from collections.abc import Callable
from pathlib import Path

from tools.emit_findings_tool import Finding, emit
from tools.read_host_tool import HostError
from tools.read_product_config_tool import ConfigError, read_product_config

__all__ = ["run_gate_command"]


def run_gate_command(
    gate: str,
    check: Callable[..., list[Finding]],
    argv: list[str] | None = None,
    description: str | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog=gate, description=description)
    parser.add_argument(
        "--root", type=Path, default=Path.cwd(), help="product root (default: current directory)"
    )
    parser.add_argument("--base", help="reference the pull request's commits start after")
    args = parser.parse_args(argv)  # exits 2 on wrong usage
    try:
        config = read_product_config(args.root)
    except ConfigError as err:
        return emit(gate, [err.to_finding()])
    try:
        if "base" in inspect.signature(check).parameters:
            return emit(gate, check(config, base=args.base))
        return emit(gate, check(config))
    except HostError as err:
        return emit(
            gate, [Finding("HOST_UNREADABLE", ".", None, f"The code host cannot be read: {err}")]
        )
