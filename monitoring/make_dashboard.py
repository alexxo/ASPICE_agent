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
LABELS = ("qf_scope", "qf_product", "qf_kind", "session_id", "model", "type")
FILTER = '{qf_scope=~"$qf_scope", qf_product=~"$qf_product"}'
SOURCE = {"type": "prometheus", "uid": "prometheus"}  # the stack's own data source
LEDGER = {"type": "frser-sqlite-datasource", "uid": "costs"}  # costs_datasource.yaml
# The ledger's rows in the filters: the products picked (All is ".*"), and the
# pull request or branch picked (All is __all); the orchestrator has neither.
# Grafana puts a filter's All value in as it is, never formatted: the quotes are
# the query's, around the values as Grafana writes them (csv: a,b).
IN_FILTER = (
    "('${qf_product:csv}' = '.*' "
    "OR ',' || '${qf_product:csv}' || ',' LIKE '%,' || product || ',%') "
    "AND ('${qf_pr}' = '__all' OR COALESCE('#' || pr, branch) = '${qf_pr}')"
)
WORK = "COALESCE('#' || pr, branch)"  # a pull request, or the branch before it
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


def sql(text: str, ref: str = "A") -> dict:
    """A query of the cost ledger."""
    return {
        "datasource": LEDGER,
        "refId": ref,
        "queryType": "table",
        "rawQueryText": text,
        "queryText": text,
        "timeColumns": [],
    }


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
# A session is what a tab started, by its kind (qf_kind): a session without one
# is the tab's own, the person's: the orchestrator in a product.
SESSION_LEGEND = "{{qf_scope}} · {{qf_kind}}"
SESSIONS = "qf_scope, qf_kind"
BY_SESSION = {"mode": "palette-classic"}


def by_session(expr: str) -> str:
    """The sessions without a kind named the orchestrator."""
    return f'label_replace({expr}, "qf_kind", "orchestrator", "qf_kind", "")'


# Every name the dashboard colours has its own colour, in every chart that
# shows it and nowhere else: a kind of session, a model family, a token type, an LLM, a
# kind of session, a stage. No two names share one, so a colour means one
# thing on the whole dashboard (tests/consistency/test_cost_monitoring.py).
# The colours are Kelly's of maximum contrast, and a few more, all readable
# on Grafana's dark and light themes.
MODEL_COLOURS = {".*opus.*": "#875692", ".*sonnet.*": "#F38400", ".*haiku.*": "#A1CAF1"}
TOKEN_COLOURS = {
    "input": "#9FE2BF",
    "output": "#FF6F91",
    "cacheRead": "#C9D1D9",
    "cacheCreation": "#B5651D",
}
LLM_COLOURS = {"claude": "#BE0032", "codex": "#C2B280", "gemini": "#848482"}
KIND_COLOURS = {  # the sessions of tools/start_session_tool.py, and the person's own
    "orchestrator": "#008856",
    "clarify": "#E68FAC",
    "tester": "#0067A5",
    "coder": "#F99379",
    "reviewer": "#604E97",
    "describe_tests": "#F6A600",
    "describe_design": "#B3446C",
    "expect_cases": "#DCD300",
}
STAGE_COLOURS = {  # the stages the started sessions work for: the only ones with cost
    "requirements": "#8DB600",
    "unit_tests": "#E25822",
    "unit_construction": "#00A6A6",
    "quality_assurance": "#D4A5FF",
}
# A session in a product has its kind's colour, the same as in Cost by kind; your
# own sessions in the framework's repository keep Grafana's green.
SESSION_COLOURS = {
    "framework · orchestrator": "#73BF69",
    **{f"product · {kind}": colour for kind, colour in KIND_COLOURS.items()},
}
SESSION_OVERRIDES = [
    {
        "matcher": {"id": "byName", "options": name},
        "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": colour}}],
    }
    for name, colour in SESSION_COLOURS.items()
]


def by_value(field: str, colours: dict) -> dict:
    """Each value of a text field its colour; a value not named stays grey."""
    options = {
        name: {"color": colour, "index": i} for i, (name, colour) in enumerate(colours.items())
    }
    return {
        "matcher": {"id": "byName", "options": field},
        "properties": [
            {"id": "mappings", "value": [{"type": "value", "options": options}]},
            {"id": "color", "value": {"mode": "fixed", "fixedColor": "text"}},
        ],
    }


def by_series(colours: dict, matcher: str = "byName") -> list:
    """Each series its colour, by its name (or a pattern of names)."""
    return [
        {
            "matcher": {"id": matcher, "options": name},
            "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": colour}}],
        }
        for name, colour in colours.items()
    ]


def bars_of(field: str) -> dict:
    """One horizontal bar per row, coloured by the row's name in field."""
    return {
        "orientation": "horizontal",
        "xField": field,
        "colorByField": field,
        "showValue": "always",
        "groupWidth": 0.7,
        "legend": {"showLegend": False, "displayMode": "list", "placement": "bottom"},
        "tooltip": {"mode": "single", "sort": "none"},
    }


class Span:
    """One section: its time span, and what its charts sum over it."""

    def __init__(self, title, since, cost, own=None, over_time=None, share=False):
        self.title = title
        self.since = since  # the panels' own time range, whatever the picker says
        self.cost = cost  # (metric, by) -> what the sessions in the filter spent in the span
        self.own = own  # (pid, y) -> the panels only this section has
        self.over_time = over_time  # what each hourly bar of Cost over time by session holds
        self.share = share  # costs as % of the 5-hour window, not dollars


def window_extras(pid: int, y: int) -> list:
    return [
        window_panel(pid, "5-hour window used", (0, y, 12, 4), "five_hour"),
        window_panel(pid + 1, "Week used", (12, y, 12, 4), "seven_day"),
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
        description="How much of the window is used, and when it resets: what Claude Code "
        "reports of your plan's allowance, sent by the status line (COST_MONITORING.md, Your "
        "plan's allowance). Orange from 80 %, red from 100 %.",
        overrides=[
            {
                "matcher": {"id": "byFrameRefID", "options": "B"},
                "properties": [
                    {"id": "unit", "value": "dateTimeFromNow"},
                    {"id": "color", "value": {"mode": "fixed", "fixedColor": "text"}},
                ],
            }
        ],
        # Values only, no names: Grafana then sizes them by the panel, whose
        # title says what they are; with names it leaves the height unused.
        options={**STAT, "textMode": "value"},
    )


def section(span: Span, pid: int, y: int) -> tuple[list, int]:
    """The same bars over the span: the section's panels, and where the next starts.

    The section's own panels, if any; then cost by session, cost by model and
    tokens by type; then, if the section has it, cost over time by session.
    """
    first, top = pid, y
    pid, y = pid + 1, y + 1
    own = span.own(pid, y) if span.own else []
    pid, y = pid + len(own), y + (4 if own else 0)
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
            "Cost by session",
            (0, y, 8, 6),
            [target(by_session(costs(SESSIONS)), SESSION_LEGEND, instant=True)],
            unit=cost["unit"],
            decimals=cost["decimals"],
            description=f"Each kind of session's {cost['description']} over the span: your "
            "own, the orchestrator, and those the framework starts; each has its colour in "
            "every chart, Cost by kind's included.",
            color=BY_SESSION,
            overrides=SESSION_OVERRIDES,
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
            description=f"Each model's {cost['description']} over the span; a model "
            "family keeps its colour (opus, sonnet, haiku).",
            overrides=by_series(MODEL_COLOURS, "byRegexp"),
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
            overrides=by_series(TOKEN_COLOURS),
            options=BARS,
        ),
    ]
    y += 6
    if span.over_time:
        panels.append(
            panel(
                pid + 3,
                "timeseries",
                "Cost over time by session",
                (0, y, 24, 8),
                [
                    target(
                        by_session(f"sum by ({SESSIONS}) ({span.over_time})"),
                        SESSION_LEGEND,
                        interval="1h",
                    )
                ],
                description="Each bar is the hour that starts at its time, stacked by kind of "
                "session; the bar of the hour running now grows as it is spent.",
                color=BY_SESSION,
                overrides=SESSION_OVERRIDES,
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


def matrix(rows: str, columns: str) -> list:
    """One bar per row, split by column, the most expensive first."""
    return [
        {
            "id": "groupingToMatrix",
            "options": {
                "rowField": rows,
                "columnField": columns,
                "valueField": "cost",
                "emptyValue": "null",
            },
        },
        {
            "id": "calculateField",
            "options": {"mode": "reduceRow", "reduce": {"reducer": "sum"}, "alias": "total"},
        },
        {"id": "sortBy", "options": {"sort": [{"field": "total", "desc": True}]}},
        {"id": "organize", "options": {"excludeByName": {"total": True}}},
    ]


STACKED = {
    "orientation": "horizontal",
    "stacking": "normal",
    "showValue": "never",
    "groupWidth": 0.7,
    "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"},
    "tooltip": {"mode": "multi", "sort": "desc"},
}


def ledger_section(pid: int, y: int) -> tuple[list, int]:
    """The cost of a stage over the whole project, from the cost ledger: every
    session the framework started, and the orchestrator, whatever their age."""
    stages = f"WHERE {IN_FILTER} AND kind != 'orchestrator'"
    panels = [
        row(pid, "Cost of a stage · whole project", y),
        panel(
            pid + 1,
            "barchart",
            "Cost by stage",
            (0, y + 1, 9, 8),
            [
                sql(
                    f"SELECT stage, SUM(cost_usd) AS cost FROM sessions {stages} "
                    "GROUP BY stage ORDER BY cost DESC"
                )
            ],
            description="What each stage's sessions cost, from the first to the last; the "
            "orchestrator, your own session, has no stage (Total). Each stage has its colour.",
            datasource=LEDGER,
            overrides=[by_value("stage", STAGE_COLOURS)],
            options=bars_of("stage"),
        ),
        panel(
            pid + 2,
            "stat",
            "Total",
            (9, y + 1, 3, 8),
            [
                sql(
                    "SELECT SUM(CASE WHEN kind != 'orchestrator' THEN cost_usd END) AS stages, "
                    "SUM(CASE WHEN kind = 'orchestrator' THEN cost_usd END) AS orchestrator "
                    f"FROM sessions WHERE {IN_FILTER}"
                )
            ],
            description="The stages' sessions, and the orchestrator beside them.",
            datasource=LEDGER,
            options={**STAT, "textMode": "value_and_name", "orientation": "vertical"},
        ),
        panel(
            pid + 3,
            "table",
            "Effort by LLM",
            (12, y + 1, 12, 8),
            [
                sql(
                    "SELECT llm AS LLM, GROUP_CONCAT(DISTINCT kind) AS Kinds, "
                    "COUNT(*) AS Sessions, SUM(seconds) / 3600.0 AS Hours, "
                    f"SUM(cost_usd) AS Cost FROM sessions WHERE {IN_FILTER} "
                    "GROUP BY llm ORDER BY Hours DESC"
                )
            ],
            unit="none",
            decimals=1,
            description="Sessions and hours compare every LLM; cost only those that report "
            "it (empty: it reports none).",
            datasource=LEDGER,
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "Cost"},
                    "properties": [
                        {"id": "unit", "value": "currencyUSD"},
                        {"id": "decimals", "value": 2},
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "Sessions"},
                    "properties": [{"id": "decimals", "value": 0}],
                },
                {
                    **by_value("LLM", LLM_COLOURS),
                    "properties": [
                        *by_value("LLM", LLM_COLOURS)["properties"],
                        {"id": "custom.cellOptions", "value": {"type": "color-text"}},
                    ],
                },
            ],
        ),
        panel(
            pid + 4,
            "barchart",
            "Cost by kind",
            (0, y + 9, 24, 8),
            [
                sql(
                    "SELECT kind, SUM(cost_usd) AS cost FROM sessions "
                    f"WHERE {IN_FILTER} GROUP BY kind ORDER BY cost DESC"
                )
            ],
            description="Who spent it: each kind of session, and the orchestrator, your own "
            "session, each with its colour. A kind run by an LLM that reports no cost has no "
            "bar: see Effort by LLM.",
            datasource=LEDGER,
            overrides=[by_value("kind", KIND_COLOURS)],
            options=bars_of("kind"),
        ),
        panel(
            pid + 5,
            "barchart",
            "Cost by pull request · split by stage",
            (0, y + 17, 24, 10),
            [
                sql(
                    f"SELECT {WORK} AS work, stage, SUM(cost_usd) AS cost FROM sessions "
                    f"{stages} GROUP BY work, stage"
                )
            ],
            description="Each pull request, or its branch before it existed, split by the "
            "stage the money went to, the most expensive first.",
            datasource=LEDGER,
            transformations=matrix("work", "stage"),
            overrides=by_series(STAGE_COLOURS),
            options=STACKED,
        ),
    ]
    return panels, y + 27


def pull_requests() -> dict:
    """The filter of the ledger's section: a pull request or branch, newest first."""
    query = (
        f"SELECT work FROM (SELECT {WORK} AS work, MAX(time) AS last FROM sessions "
        "WHERE stage IS NOT NULL GROUP BY work) WHERE work IS NOT NULL ORDER BY last DESC"
    )
    return {
        "name": "qf_pr",
        "label": "Pull request",
        "type": "query",
        "datasource": LEDGER,
        "query": query,
        "definition": query,
        "refresh": 2,
        "includeAll": True,
        "multi": False,
        "allValue": "__all",
        "current": {"text": "All", "value": "$__all"},
        "sort": 0,
    }


def dashboard() -> dict:
    panels, pid, y = [], 1, 0
    for span in SPANS:
        made, y = section(span, pid, y)
        panels += made
        pid += len(made)
    made, y = ledger_section(pid, y)
    panels += made
    return {
        "uid": "claude-costs",
        "title": "Claude costs",
        "tags": ["claude", "cost"],
        "timezone": "browser",
        "refresh": "1m",
        "schemaVersion": 39,
        "editable": True,
        "time": {"from": "now/d", "to": "now"},  # each section keeps its own span
        "description": "What Claude Code spends now, in the 5-hour window and today, per kind "
        "of session; "
        "and what each stage, kind, LLM and pull request cost over the whole project. "
        "Dollars are API list prices: on a subscription they compare, they are not billed.",
        "templating": {
            "list": [
                variable("qf_scope", "Scope"),
                variable("qf_product", "Product"),
                pull_requests(),
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
