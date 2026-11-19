"""Status line that shows the subscription's usage and sends it to the stack.

Claude Code runs a status line command with the session's data on stdin; on a
Pro, Max or Ultra plan that data holds how much of the 5-hour and the weekly
allowance is used, and when each resets (`rate_limits`). This prints them,
e.g. `5h 42 % (21:10) · week 18 % (Mon 09:00)`, and sends them to the stack
as two gauges, `qf_plan_used_percent` and `qf_plan_resets_at`, one series per
window (COST_MONITORING.md, *Your plan's allowance*). The allowance is the
account's, so one tab that runs this counts every session.

In a product's folder (one holding qf.yaml) with QF_COSTS_DIR set, it also
keeps this session's cost in the cost ledger as the orchestrator's row: one
row per session, its cost the running total, written when it changes
(tools/write_cost_ledger_tool.py; COST_MONITORING.md, *The cost of a stage*).

Nothing here may slow or break the status line: a stack that is down, a
ledger that cannot be written, or data without `rate_limits`, only leaves
the gauges or the row unwritten.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = os.environ.get("QF_PLAN_USAGE_ENDPOINT", "http://localhost:4318/v1/metrics")
WINDOWS = {"five_hour": "5h", "seven_day": "week"}
EVERY = 10  # seconds between two sends; the status line runs far more often
SENT = Path(os.environ.get("TMPDIR", "/tmp")) / "qf_plan_usage_sent"
FRAMEWORK = Path(__file__).resolve().parents[1]


def windows(data: dict) -> dict:
    """{window: (used %, resets at)} for the windows Claude Code reports."""
    limits = data.get("rate_limits") or {}
    found = {}
    for name in WINDOWS:
        w = limits.get(name) or {}
        if w.get("used_percentage") is not None and w.get("resets_at"):
            found[name] = (float(w["used_percentage"]), int(w["resets_at"]))
    return found


def line(found: dict) -> str:
    parts = []
    for name, short in WINDOWS.items():
        if name in found:
            used, resets = found[name]
            at = datetime.fromtimestamp(resets).strftime(
                "%H:%M" if name == "five_hour" else "%a %H:%M"
            )
            parts.append(f"{short} {used:.0f} % ({at})")
    return " · ".join(parts)


def gauge(name: str, found: dict, index: int, now: str) -> dict:
    points = [
        {
            "asDouble": values[index],
            "timeUnixNano": now,
            "attributes": [{"key": "window", "value": {"stringValue": window}}],
        }
        for window, values in found.items()
    ]
    return {"name": name, "gauge": {"dataPoints": points}}


def send(found: dict) -> None:
    try:
        if time.time() - SENT.stat().st_mtime < EVERY:
            return
    except OSError:
        pass
    now = str(time.time_ns())
    body = {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "qf-plan-usage"}}
                    ]
                },
                "scopeMetrics": [
                    {
                        "metrics": [
                            gauge("qf_plan_used_percent", found, 0, now),
                            gauge("qf_plan_resets_at", found, 1, now),
                        ]
                    }
                ],
            }
        ]
    }
    request = urllib.request.Request(
        ENDPOINT, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(request, timeout=1).close()
        SENT.touch()
    except OSError:
        pass  # the stack is down: the status line still shows


def product_of(data: dict) -> Path | None:
    """The product the session works in: the folder holding qf.yaml, from its own up."""
    here = Path((data.get("workspace") or {}).get("current_dir") or data.get("cwd") or ".")
    return next((p for p in (here, *here.parents) if (p / "qf.yaml").is_file()), None)


def record(data: dict) -> None:
    """The orchestrator's row in the cost ledger, when its cost changed."""
    folder = os.environ.get("QF_COSTS_DIR")
    cost = data.get("cost") or {}
    session = data.get("session_id")
    if not folder or not session or cost.get("total_cost_usd") is None:
        return
    product = product_of(data)
    if product is None:
        return
    seen = Path(os.environ.get("TMPDIR", "/tmp")) / f"qf_cost_{session}"
    total = str(cost["total_cost_usd"])
    try:
        if seen.read_text() == total:
            return
    except OSError:
        pass
    sys.path.insert(0, str(FRAMEWORK))
    from tools.write_cost_ledger_tool import write_row

    repo = (data.get("workspace") or {}).get("repo") or {}
    row = {
        "id": session,
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "product": repo.get("name") or product.name,
        "kind": "orchestrator",
        "llm": "claude",
        "model": (data.get("model") or {}).get("id"),
        "seconds": round((cost.get("total_duration_ms") or 0) / 1000, 1),
        "cost_usd": cost["total_cost_usd"],
        "timed_out": 0,
    }
    try:
        write_row(Path(folder), row)
        seen.write_text(total)
    except Exception:  # the status line still shows
        pass


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    record(data)
    found = windows(data)
    if found:
        send(found)
        print(line(found))


if __name__ == "__main__":
    main()
