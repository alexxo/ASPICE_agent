"""scan_security_gate — principle #29: no leaked secret, no vulnerable dependency, merged.

The stack declares two scanners under security_scans — secrets and
dependencies — each with a pinned version (TOOL_VERSION_MISMATCH, as for the
checks) and SARIF results; each runs once per tree. Both must write their
results (SCAN_NOT_RUN): a scanner exits non-zero when it finds something, so
the results decide, not the exit code. No result may be critical or high
(SECURITY_FINDING): one whose security-severity, on the result or on its rule,
is 7.0 or more — or one with no score at all, since a found secret has none and
always blocks (decision 8 of the quality assurance stage).

    python gates/sup/scan_security_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack, run_command  # noqa: E402

GATE = "scan_security_gate"
HIGH = 7.0  # CVSS: 7.0–8.9 high, 9.0–10.0 critical


def check(config: ProductConfig) -> list[Finding]:
    stack = read_stack(config)
    if stack is None:
        return []  # check_stack_decision_gate reports a missing or broken stack
    shown = config.relative(config.stack_file)
    findings: list[Finding] = []
    for kind, entry in stack["security_scans"].items():
        run = run_command(config, "security_scans", kind, entry)
        label = f"security_scans.{kind}"
        if not (run.version_exit == 0 and entry["version"].lstrip("v") in run.version_output):
            findings.append(
                Finding(
                    "TOOL_VERSION_MISMATCH",
                    shown,
                    None,
                    f"{label}: '{entry['version_command']}' does not report {entry['tool']} "
                    f"{entry['version']}; it said: {_tail(run.version_output)}",
                )
            )
        results = [_read(Path(p)) for p in run.results]
        if not results or any(r is None for r in results):
            findings.append(
                Finding(
                    "SCAN_NOT_RUN",
                    shown,
                    None,
                    f"{label} ({entry['run']}) exited {run.exit_code} without readable SARIF "
                    f"at {entry['results']}: {_tail(run.output)}",
                )
            )
            continue
        for sarif in results:
            findings += [
                Finding("SECURITY_FINDING", _relative(config, file), line, f"{label}: {text}")
                for file, line, text in blocking(sarif)
            ]
    return findings


def blocking(sarif: dict) -> list[tuple[str, int | None, str]]:
    """The critical and high results of a SARIF log: (file, line, message)."""
    found = []
    for run in sarif.get("runs") or ():
        tool = run.get("tool") or {}
        rules = {}
        for component in [tool.get("driver") or {}, *(tool.get("extensions") or ())]:
            for rule in component.get("rules") or ():
                rules[rule.get("id")] = rule
        for result in run.get("results") or ():
            rule = rules.get(result.get("ruleId")) or {}
            score = _score(result) if _score(result) is not None else _score(rule)
            if score is not None and score < HIGH:
                continue
            file, line = _where(result)
            text = (result.get("message") or {}).get("text") or "finding"
            grade = "unscored" if score is None else f"severity {score:g}"
            found.append((file, line, f"{result.get('ruleId') or 'rule'} ({grade}): {text}"))
    return found


def _score(item: dict) -> float | None:
    value = (item.get("properties") or {}).get("security-severity")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _where(result: dict) -> tuple[str, int | None]:
    for location in result.get("locations") or ():
        physical = location.get("physicalLocation") or {}
        uri = (physical.get("artifactLocation") or {}).get("uri")
        if uri:
            line = (physical.get("region") or {}).get("startLine")
            return uri.removeprefix("file://"), line if isinstance(line, int) and line > 0 else None
    return ".", None


def _relative(config: ProductConfig, uri: str) -> str:
    return config.relative(Path(uri)) if Path(uri).is_absolute() else uri


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _tail(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1][:200] if lines else "no output"


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
