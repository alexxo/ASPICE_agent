# Cost monitoring for product developers

**For:** you build a product with the framework, on your own computer, as one
user of it. You work with the ASPICE Agent in the product's folder, and you
run the review watcher there.

**Not for:** developing the framework itself. That setup has a second user on
the same computer: [`COST_MONITORING_FOR_FRAMEWORK_MAINTAINERS.md`](COST_MONITORING_FOR_FRAMEWORK_MAINTAINERS.md).

What the stack is, what it shows and what to do when something goes wrong
are in [`COST_MONITORING_COMMON_STACK.md`](COST_MONITORING_COMMON_STACK.md).
This guide says who runs what, and where each setting goes, step by step.

## Who runs what

One user of your computer runs everything: you, signed in as yourself.

| What | Runs | Reads its settings from |
|---|---|---|
| Your session with the agent, the orchestrator | in a terminal, in the product's folder | `<product>/.claude/settings.local.json`, and the product's `.env` for the ledger |
| The sessions the agent starts: clarify, tester, coder | started by the agent | the product's `.env` |
| The review watcher and its sessions: reviewer, describe | in a second terminal, in the product's folder | `~/.aspice_agent_secrets/.env`, in the home folder of the user who starts it |

So the product's clone, `~/.aspice_agent_secrets/` and the stack's data folder
belong to that one user (QUICKSTART step 8). Every setting sits in a file that
each session reads when it starts: none in a terminal's own settings, so it
does not matter which terminal you start from.

## Setup

The placeholders are those of the common stack: `<data folder>`, `<product>`
and `<product name>`.

### 1. Build the stack

[`COST_MONITORING_COMMON_STACK.md`](COST_MONITORING_COMMON_STACK.md),
*One-time setup*, steps 1 to 6.

### 2. The sessions the framework starts

Add these lines to the product's `.env`:

```
CLAUDE_CODE_ENABLE_TELEMETRY=1
OTEL_METRICS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_METRIC_EXPORT_INTERVAL=10000
OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative
OTEL_RESOURCE_ATTRIBUTES=qf.scope=product,qf.product=<product name>,qf.session=developer
QF_COSTS_DIR=<data folder>/costs
```

and the same lines to `~/.aspice_agent_secrets/.env`, with
`qf.session=watcher`. Each Claude command line in the two files needs
`--output-format json` (QUICKSTART step 8): without it a session's ledger row
has no cost. Restart the watcher: it reads its `.env` when it starts.

### 3. Your own session

Write `<product>/.claude/settings.local.json` (git ignores `.claude/` in a
product; if the file exists, add the two keys to it):

```json
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
    "OTEL_METRIC_EXPORT_INTERVAL": "10000",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "cumulative",
    "OTEL_RESOURCE_ATTRIBUTES": "qf.scope=product,qf.product=<product name>,qf.session=developer"
  },
  "statusLine": {
    "type": "command",
    "command": "python3 <product>/.framework/monitoring/plan_usage_statusline.py"
  }
}
```

(`python` where `python3` is missing; on Windows, `<product>` with
backslashes.) `env` sends your session's numbers; `statusLine` shows your
plan's allowance and keeps your session's row in the ledger, from the
`QF_COSTS_DIR` of step 2. Both apply to the sessions you start in this
product only: another product keeps its own file, and the sessions the
framework starts never read it (their command lines read your user settings
only), so they keep their own labels.

Quit Claude and start it again in the product's folder.

### 4. Check

Give the agent one prompt. Under the prompt, the status line shows your
allowance, e.g. `5h 42 % (21:10) · week 18 % (Sat 09:00)`. It shows
`cost not recorded: <reason>` when the ledger cannot be written: fix what it
names (*When something goes wrong* in the common stack). Then run the check of
*The cost of a stage* in the common stack: the newest row is your session's.

When you set this up with the agent (QUICKSTART step 10), the agent runs that
check itself, and step 10 is done only once your session's row is there.
