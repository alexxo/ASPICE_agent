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
METRICS = (COST, TOKENS)  # every metric of Claude Code the dashboard reads
USED = "qf_plan_used_percent"  # sent by plan_usage_statusline.py
RESETS = "qf_plan_resets_at"
PLAN = (USED, RESETS)
LABELS = ("qf_scope", "qf_product", "qf_session", "session_id", "model", "type")
FILTER = '{qf_scope=~"$qf_scope", qf_product=~"$qf_product"}'
SOURCE = {"type": "prometheus", "uid": "prometheus"}  # the stack's own data source
OUT = Path(__file__).resolve().parent / "claude-costs.json"


def spent(metric: str, window: str, where: str = FILTER, before: str = "2d") -> str:
    """What the sessions spent in the window.

    `before` is how far back a session's value before the window is looked
    for; a session sends every 10 seconds while it runs.
    """
    m = metric + where
    return (
        f"(max_over_time({m}[{window}]) - "
        f"(last_over_time({m}[{before}] offset {window}) or max_over_time({m}[{window}]) * 0))"
    )


def plan(metric: str, window: str) -> str:
    """The last value the status line sent for the window of the plan."""
    return f'max(last_over_time({metric}{{window="{window}"}}[7d]))'


def used(window: str) -> str:
    """How much of the window is used: 0 once it has reset, none if never sent."""
    resets = plan(RESETS, window)
    return f"(({plan(USED, window)} and on() ({resets} > time())) or on() ({resets} <= time()) * 0)"


WINDOW_START = f'(max(last_over_time({RESETS}{{window="five_hour"}}[7d] @ end())) - 18000)'


def in_window(metric: str = COST, where: str = "", by: str = "") -> str:
    """What the sessions spent since the 5-hour window started.

    Summed minute by minute from the window's start. Without `where`, every
    session counts, not only those in the filter: the allowance is the account's.
    """
    minute = total(spent(metric, "1m", where, "15m"), by)
    return f"sum_over_time(({minute} and on() (time() >= {WINDOW_START}))[5h:1m])"


def total(expr: str, by: str = "") -> str:
    return f"sum by ({by}) ({expr})" if by else f"sum({expr})"


# What 1 % of the 5-hour window costs at list price: the dollars of every
# session since it started, divided by the % of it used. An estimate, since the
# allowance is not set in dollars; it moves a lot while the window is nearly empty.
PER_PERCENT = f"({in_window()} / ({used('five_hour')} > 0))"


def spent_from(metric: str, window: str) -> str:
    """What the sessions spent in the window that starts at the point's time.

    A bar then stands on its window's start, so the window still running has
    one too, growing as it is spent.
    """
    m = metric + FILTER
    ahead = f"max_over_time({m}[{window}] offset -{window})"
    return f"({ahead} - (last_over_time({m}[2d]) or {ahead} * 0))"


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
    if kind == "bargauge":  # bars from zero, not from the smallest value
        p["fieldConfig"]["defaults"]["min"] = 0
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


class Span:
    """One section: its time span, and what its charts sum over it."""

    def __init__(self, title, since, cost, own=None, over_time=None, share=False):
        self.title = title
        self.since = since  # the panels' own time range, whatever the picker says
        self.cost = cost  # (metric, by) -> what the sessions in the filter spent in the span
        self.own = own  # (pid, y) -> the panels only this section has
        self.over_time = over_time  # what each hourly bar of Cost over time by tab holds
        self.share = share  # costs as % of the 5-hour window, not dollars


def window_extras(pid: int, y: int) -> list:
    return [
        window_panel(pid, "5-hour window used", (0, y, 6, 4), "five_hour"),
        window_panel(pid + 1, "Week used", (6, y, 6, 4), "seven_day"),
    ]


SPANS = (
    Span("Now · last 15 min", "15m", lambda metric, by: total(spent(metric, "15m"), by)),
    Span(
        "5-hour window",
        "5h",
        lambda metric, by: in_window(metric, FILTER, by),
        own=window_extras,
        share=True,
    ),
    Span(
        "Today",
        "now/d",
        lambda metric, by: total(spent(metric, "$__range"), by),
        over_time=spent_from(COST, "1h"),
    ),
)


def window_panel(pid: int, title: str, place: tuple, window: str) -> dict:
    """How much of a window of the plan is used, and when it resets."""
    return panel(
        pid,
        "stat",
        title,
        place,
        [
            target(used(window), "used", instant=True),
            target(f"{plan(RESETS, window)} * 1000", "resets", ref="B", instant=True),
        ],
        unit="percent",
        decimals=0,
        thresholds=LIMIT,
        description="What Claude Code reports of your plan's allowance, sent by the status "
        "line (COST_MONITORING.md, Your plan's allowance). Orange from 80 %, red from 100 %.",
        overrides=[
            {
                "matcher": {"id": "byFrameRefID", "options": "B"},
                "properties": [
                    {"id": "unit", "value": "dateTimeFromNow"},
                    {"id": "color", "value": {"mode": "fixed", "fixedColor": "text"}},
                ],
            }
        ],
        options={**STAT, "textMode": "value_and_name"},
    )


def section(span: Span, pid: int, y: int) -> tuple[list, int]:
    """The same bars over the span: the section's panels, and where the next starts.

    The section's own panels, if any; then cost by tab, cost by model and
    tokens by type; then, if the section has it, cost over time by tab.
    """
    first, top = pid, y
    pid, y = pid + 1, y + 1
    own = span.own(pid, y) if span.own else []
    pid, y = pid + len(own), y + (4 if own else 0)
    tabs = "qf_scope, qf_session"
    cost = {"unit": "currencyUSD", "decimals": 2, "description": "list-price cost"}
    if span.share:
        cost = {"unit": "percent", "decimals": 0, "description": "share of the 5-hour window"}

    def costs(by: str) -> str:
        expr = span.cost(COST, by)
        return f"{expr} / on() group_left() {PER_PERCENT}" if span.share else expr

    panels = [
        *own,
        panel(
            pid,
            "bargauge",
            "Cost by tab",
            (0, y, 8, 6),
            [target(costs(tabs), TAB_LEGEND, instant=True)],
            unit=cost["unit"],
            decimals=cost["decimals"],
            description=f"Each tab's {cost['description']} over the span; a tab has one colour "
            "in every chart.",
            color=BY_TAB,
            overrides=TAB_OVERRIDES,
            options=BARS,
        ),
        panel(
            pid + 1,
            "bargauge",
            "Cost by model",
            (8, y, 8, 6),
            [target(costs("model"), "{{model}}", instant=True)],
            unit=cost["unit"],
            decimals=cost["decimals"],
            description=f"Each model's {cost['description']} over the span.",
            options=BARS,
        ),
        panel(
            pid + 2,
            "bargauge",
            "Tokens by type",
            (16, y, 8, 6),
            [target(span.cost(TOKENS, "type"), "{{type}}", instant=True)],
            unit="short",
            decimals=1,
            description="cacheRead is cheap context reuse; input and output cost most per token.",
            options=BARS,
        ),
    ]
    y += 6
    if span.over_time:
        panels.append(
            panel(
                pid + 3,
                "timeseries",
                "Cost over time by tab",
                (0, y, 24, 8),
                [target(f"sum by ({tabs}) ({span.over_time})", TAB_LEGEND, interval="1h")],
                description="Each bar is the hour that starts at its time, stacked by tab; "
                "the bar of the hour running now grows as it is spent.",
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
            )
        )
        y += 8
    for p in panels:
        p["timeFrom"] = span.since
    return [row(first, span.title, top), *panels], y


def dashboard() -> dict:
    panels, pid, y = [], 1, 0
    for span in SPANS:
        made, y = section(span, pid, y)
        panels += made
        pid += len(made)
    return {
        "uid": "claude-costs",
        "title": "Claude costs",
        "tags": ["claude", "cost"],
        "timezone": "browser",
        "refresh": "1m",
        "schemaVersion": 39,
        "editable": True,
        "time": {"from": "now/d", "to": "now"},  # each section keeps its own span
        "description": "What Claude Code spends now, in the 5-hour window and today, per tab. "
        "Dollars are API list prices: on a subscription they compare, they are not billed.",
        "templating": {
            "list": [
                variable("qf_scope", "Scope"),
                variable("qf_product", "Product"),
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
