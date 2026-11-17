"""Write the cost dashboard, claude-costs.json, next to this file.

The dashboard is generated, never edited in Grafana: change a panel here, then
run `python make_dashboard.py` in this folder (`python3` where `python` is
missing). Every cost is what a session spent in a window — its highest value
in the window minus what it had before — because increase() drops a new
session's first value (COST_MONITORING.md, *Why the numbers are exact*).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

COST = "claude_code_cost_usage_USD_total"
TOKENS = "claude_code_token_usage_tokens_total"
METRICS = (COST, TOKENS)  # every metric the dashboard reads
LABELS = ("qf_scope", "qf_product", "qf_session", "session_id", "model", "type")
FILTER = '{qf_scope=~"$qf_scope", qf_product=~"$qf_product"}'
SOURCE = {"type": "prometheus", "uid": "prometheus"}  # the stack's own data source
OUT = Path(__file__).resolve().parent / "claude-costs.json"


def spent(metric: str, window: str) -> str:
    """What the sessions spent in the window."""
    m = metric + FILTER
    return (
        f"(max_over_time({m}[{window}]) - "
        f"(last_over_time({m}[2d] offset {window}) or max_over_time({m}[{window}]) * 0))"
    )


def target(expr, legend="", ref="A", instant=False, interval=None, table=False) -> dict:
    t = {
        "datasource": SOURCE,
        "expr": expr,
        "legendFormat": legend,
        "refId": ref,
        "instant": instant,
        "range": not instant,
        "format": "table" if table else "time_series",
    }
    if interval:
        t["interval"] = interval
    return t


def panel(pid, kind, title, place, targets, unit="currencyUSD", decimals=2, **extra) -> dict:
    x, y, w, h = place
    p = {
        "id": pid,
        "type": kind,
        "title": title,
        "description": extra.pop("description", ""),
        "datasource": SOURCE,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": targets,
        "fieldConfig": {"defaults": {"unit": unit, "decimals": decimals}, "overrides": []},
        "options": {},
    }
    color = extra.pop("color", None)
    p["fieldConfig"]["overrides"] = extra.pop("overrides", [])
    custom = extra.pop("custom", None)
    thresholds = extra.pop("thresholds", None)
    if color:
        p["fieldConfig"]["defaults"]["color"] = color
    if custom:
        p["fieldConfig"]["defaults"]["custom"] = custom
    if thresholds:
        p["fieldConfig"]["defaults"]["thresholds"] = thresholds
    p.update(extra)
    return p


def row(pid: int, title: str, y: int) -> dict:
    return {
        "id": pid,
        "type": "row",
        "title": title,
        "collapsed": False,
        "gridPos": {"x": 0, "y": y, "w": 24, "h": 1},
        "panels": [],
    }


def variable(name: str, label: str) -> dict:
    query = f"label_values({COST}, {name})"
    return {
        "name": name,
        "label": label,
        "type": "query",
        "datasource": SOURCE,
        "query": {"query": query, "refId": name},
        "definition": query,
        "refresh": 2,
        "includeAll": True,
        "multi": True,
        "allValue": ".*",
        "current": {"text": "All", "value": "$__all"},
        "sort": 1,
    }


STAT = {
    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
    "colorMode": "value",
    "graphMode": "none",
    "textMode": "value",
}
BARS = {
    "orientation": "horizontal",
    "displayMode": "basic",
    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
}
LIMIT = {
    "mode": "absolute",
    "steps": [
        {"color": "green", "value": None},
        {"color": "orange", "value": 80},
        {"color": "red", "value": 100},
    ],
}
TAB = "qf_scope, qf_product, qf_session"
TAB_LEGEND = "{{qf_scope}} · {{qf_session}}"
# A tab keeps one colour in every chart: those it had before, in Grafana's own
# order (green, yellow, blue); another tab takes the next colour of that order.
TAB_COLOURS = {
    "framework · developer": "green",
    "product · developer": "yellow",
    "product · watcher": "blue",
}
BY_TAB = {"mode": "palette-classic"}
TAB_OVERRIDES = [
    {
        "matcher": {"id": "byName", "options": name},
        "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": colour}}],
    }
    for name, colour in TAB_COLOURS.items()
]


def dashboard() -> dict:
    today = "$__range"
    panels = [
        row(1, "Now", 0),
        panel(
            2,
            "stat",
            "Spend rate, last 15 min ($/min)",
            (0, 1, 6, 5),
            [target(f"sum({spent(COST, '15m')}) / 15", instant=True)],
            description="Dollars per minute over the last 15 minutes, every tab in the filter.",
            options=STAT,
        ),
        panel(
            3,
            "stat",
            "Sessions spending now",
            (6, 1, 6, 5),
            [
                target(
                    f"count(sum by (session_id) ({spent(COST, '5m')}) > 0) or vector(0)",
                    instant=True,
                )
            ],
            unit="none",
            decimals=0,
            description="Sessions whose cost grew in the last 5 minutes.",
            options=STAT,
        ),
        panel(
            4,
            "table",
            "By tab",
            (12, 1, 12, 5),
            [
                target(f"sum by ({TAB}) ({spent(COST, '15m')})", instant=True, table=True),
                target(f"sum by ({TAB}) ({spent(COST, today)})", ref="B", instant=True, table=True),
            ],
            description="Each tab's cost in the last 15 minutes and in the time range.",
            transformations=[
                {"id": "merge", "options": {}},
                {
                    "id": "organize",
                    "options": {
                        "excludeByName": {"Time": True},
                        "indexByName": {
                            "qf_scope": 0,
                            "qf_product": 1,
                            "qf_session": 2,
                            "Value #A": 3,
                            "Value #B": 4,
                        },
                        "renameByName": {
                            "qf_scope": "Scope",
                            "qf_product": "Product",
                            "qf_session": "Tab",
                            "Value #A": "Last 15 min",
                            "Value #B": "Today",
                        },
                    },
                },
                {"id": "sortBy", "options": {"sort": [{"field": "Today", "desc": True}]}},
            ],
        ),
        row(5, "Today", 6),
        panel(
            6,
            "stat",
            "Cost today",
            (0, 7, 6, 5),
            [target(f"sum({spent(COST, today)})", instant=True)],
            description="Every session in the filter, over the time range (today by default).",
            options=STAT,
        ),
        panel(
            7,
            "stat",
            "Of the daily limit",
            (6, 7, 6, 5),
            [target(f"sum({spent(COST, today)}) / $daily_limit * 100", instant=True)],
            unit="percent",
            decimals=0,
            thresholds=LIMIT,
            description="Cost today against the daily limit at the top. Orange from 80 %, "
            "red from 100 %. It only warns: nothing is stopped.",
            options={**STAT, "colorMode": "background"},
        ),
        panel(
            8,
            "bargauge",
            "Cost by model",
            (12, 7, 12, 5),
            [target(f"sum by (model) ({spent(COST, today)})", "{{model}}", instant=True)],
            options=BARS,
        ),
        panel(
            9,
            "timeseries",
            "Cost per hour",
            (0, 12, 16, 9),
            [
                target(
                    f"sum by (qf_scope, qf_session) ({spent(COST, '1h')})",
                    TAB_LEGEND,
                    interval="1h",
                )
            ],
            description="Each bar is the hour that ends at its time, stacked by tab.",
            color=BY_TAB,
            overrides=TAB_OVERRIDES,
            custom={
                "drawStyle": "bars",
                "fillOpacity": 80,
                "lineWidth": 1,
                "stacking": {"mode": "normal", "group": "A"},
            },
            options={
                "legend": {"displayMode": "table", "placement": "right", "calcs": ["sum"]},
                "tooltip": {"mode": "multi", "sort": "desc"},
            },
        ),
        panel(
            10,
            "bargauge",
            "Tokens today by type",
            (16, 12, 8, 9),
            [target(f"sum by (type) ({spent(TOKENS, today)})", "{{type}}", instant=True)],
            unit="short",
            decimals=1,
            description="cacheRead is cheap context reuse; input and output cost most per token.",
            options=BARS,
        ),
        panel(
            11,
            "bargauge",
            "Cost today by tab",
            (0, 21, 24, 6),
            [
                target(
                    f"sum by (qf_scope, qf_session) ({spent(COST, today)})",
                    TAB_LEGEND,
                    instant=True,
                )
            ],
            description="Each tab's cost over the time range, coloured as in Cost per hour.",
            color=BY_TAB,
            overrides=TAB_OVERRIDES,
            options=BARS,
        ),
    ]
    return {
        "uid": "claude-costs",
        "title": "Claude costs",
        "tags": ["claude", "cost"],
        "timezone": "browser",
        "refresh": "1m",
        "schemaVersion": 39,
        "editable": True,
        "time": {"from": "now/d", "to": "now"},
        "description": "What Claude Code spends now and today, per tab. Dollars are API list "
        "prices: on a subscription they compare, they are not billed.",
        "templating": {
            "list": [
                variable("qf_scope", "Scope"),
                variable("qf_product", "Product"),
                {
                    "name": "daily_limit",
                    "label": "Daily limit ($)",
                    "type": "textbox",
                    "query": "50",
                    "current": {"text": "50", "value": "50"},
                },
            ]
        },
        "panels": panels,
    }


def render() -> str:
    return json.dumps(dashboard(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    out.write_text(render(), encoding="utf-8")
    print(f"wrote {out}")
