# Cost monitoring: the common stack

**Start with the guide for your role**, then come back here for the parts it
names:

- [`COST_MONITORING_FOR_PRODUCT_DEVELOPERS.md`](COST_MONITORING_FOR_PRODUCT_DEVELOPERS.md):
  you build a product with the framework, as one user of your computer. This
  is the usual case.
- [`COST_MONITORING_FOR_FRAMEWORK_MAINTAINERS.md`](COST_MONITORING_FOR_FRAMEWORK_MAINTAINERS.md):
  you develop the framework itself and run a product on the same computer,
  as a second user.

Your role's guide says who runs what and where each setting goes. This one
holds what both share: what the stack is, how to build it, what it shows, and
what to do when something goes wrong.

Cost monitoring is an optional companion of the framework. It sets up a local Grafana that shows
what the LLM sessions of a product cost, now and today, per kind of session and
per model,
and what each stage, kind of session, LLM and pull request cost over the
whole project. Nothing in the framework needs it: no gate or rule reads it,
and a product works the same without it.

```
LLM sessions ──OpenTelemetry (OTLP :4317)──▶ container "lgtm" ──▶ Grafana :3000
(your tabs, the watcher,                      collector, Prometheus   dashboard "Claude costs"
 the sessions the framework starts)           data in <data folder>
```

- **OpenTelemetry** carries the numbers. The LLM's command line sends them;
  it stores and shows nothing.
- **The `lgtm` container** (Grafana's `otel-lgtm` image) receives them,
  stores them in Prometheus, and shows them in Grafana. One container, on
  your computer, reachable from this computer only.
- **The dashboard** is a file of the framework, `claude-costs.json` in this
  folder. Grafana reads it from the product's `.framework`, so a framework
  bump brings its new version.

The numbers come from Claude Code, which reports its own cost and tokens. Other
LLM command lines report other numbers, or none: see *Limits*.

## What you get

Dashboard **Claude costs**, in three live sections with the same bars, each
over its own span, whatever the time picker says, and a fourth over the whole
project, *Cost of a stage* (its own heading below):

| Section | Span | Also |
|---|---|---|
| Now · last 15 min | the last 15 minutes | |
| 5-hour window | since your plan's current 5-hour window started | 5-hour window used · Week used, and when each resets (*Your plan's allowance*); costs in % of the window |
| Today | since 00:00 | Cost over time by session: stacked bars per hour |

| Bars | Shows |
|---|---|
| Cost by session | Dollars of each kind of session: your own, the orchestrator, and each kind the framework starts |
| Cost by model | Dollars of each model |
| Tokens by type | input, output, cacheRead, cacheCreation |

A **session** is shown by its kind: the sessions the framework starts by
theirs (`qf_kind`: clarify, tester, coder, reviewer, describe_tests,
describe_design, expect_cases), and your own, which has none, as the
**orchestrator** — *framework · orchestrator* in the framework's repository.
Every name the dashboard colours has its own colour, the same in every chart
that shows it: a kind of session in *Cost by session* and in *Cost by kind*,
a stage, an LLM, a model family, a token type. At the top, **Scope** and
**Product** filter every chart but the allowance, which is your account's;
**Pull request** filters *Cost of a stage* only.

## One-time setup

Each computer that runs sessions gets its own stack. The commands use three
placeholders:

- `<data folder>`: where the numbers are kept, outside the container, e.g.
  `~/qf-monitoring` (Windows: `C:\qf-monitoring`). Removing or updating the
  container keeps them.
- `<product>`: the product's folder, which holds `.framework`. A framework
  maintainer mounts the dashboard from the framework's repository instead:
  their guide names the two lines that change.
- `<product name>`: the product's repository name, e.g.
  `Team_repo_wp_publisher`: the cost ledger names the product by it, so the
  Product filter picks the same product in every section.

On macOS with Colima, both folders must be inside your home folder: Colima
shares only that one with containers. A folder elsewhere (e.g. `/tmp`) is
mounted from Colima's own disk, and the numbers never reach your Mac.

### 1. Install a container runtime

| macOS | Linux | Windows |
|---|---|---|
| Colima: `brew install colima docker`, then `colima start --cpu 2 --memory 4`. Or Docker Desktop. | Docker Engine, as your distribution installs it. | Docker Desktop, with WSL 2. |

Then, in any terminal: `docker info --format '{{.ServerVersion}}'` must print
a version number.

### 2. Create the data folder

macOS and Linux:

```sh
mkdir -p <data folder>/grafana <data folder>/prometheus <data folder>/costs
```

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force <data folder>\grafana, <data folder>\prometheus, <data folder>\costs
```

### 3. Check the framework holds this folder

`<product>/.framework/monitoring/claude-costs.json` must exist. It does from
framework 5.1.0 on; an older pin has no dashboard to mount.

### 4. Create and start the container

It starts again on its own whenever the container runtime starts. The image
tag is the version this guide was tested with.

macOS and Linux:

```sh
docker run -d --name lgtm --restart unless-stopped \
  -p 127.0.0.1:3000:3000 -p 127.0.0.1:4317:4317 -p 127.0.0.1:4318:4318 \
  -v "<data folder>/grafana:/data/grafana" \
  -v "<data folder>/prometheus:/data/prometheus" \
  -v "<product>/.framework/monitoring:/otel-lgtm/claude-dashboards:ro" \
  -v "<product>/.framework/monitoring/provider.yaml:/otel-lgtm/grafana/conf/provisioning/dashboards/claude-costs.yaml:ro" \
  -v "<data folder>/costs:/data/costs" \
  -v "<product>/.framework/monitoring/costs_datasource.yaml:/otel-lgtm/grafana/conf/provisioning/datasources/costs.yaml:ro" \
  -e GF_PATHS_DATA=/data/grafana \
  -e GF_PLUGINS_PREINSTALL=frser-sqlite-datasource@4.0.6 \
  grafana/otel-lgtm:0.41.0
```

Windows (PowerShell):

```powershell
docker run -d --name lgtm --restart unless-stopped `
  -p 127.0.0.1:3000:3000 -p 127.0.0.1:4317:4317 -p 127.0.0.1:4318:4318 `
  -v "<data folder>\grafana:/data/grafana" `
  -v "<data folder>\prometheus:/data/prometheus" `
  -v "<product>\.framework\monitoring:/otel-lgtm/claude-dashboards:ro" `
  -v "<product>\.framework\monitoring\provider.yaml:/otel-lgtm/grafana/conf/provisioning/dashboards/claude-costs.yaml:ro" `
  -v "<data folder>\costs:/data/costs" `
  -v "<product>\.framework\monitoring\costs_datasource.yaml:/otel-lgtm/grafana/conf/provisioning/datasources/costs.yaml:ro" `
  -e GF_PATHS_DATA=/data/grafana `
  -e GF_PLUGINS_PREINSTALL=frser-sqlite-datasource@4.0.6 `
  grafana/otel-lgtm:0.41.0
```

The ports listen on this computer only (`127.0.0.1`). Grafana has no sign-in
in this image — whoever reaches port 3000 is its admin — so never publish
the ports to the network.

### 5. Check it is up

About 30 seconds the first time:

```sh
curl -s http://localhost:3000/api/health
```

(PowerShell: `Invoke-RestMethod http://localhost:3000/api/health`.) It answers
with `"database": "ok"`. Then open http://localhost:3000/d/claude-costs: the
dashboard is there, empty until a session sends numbers.

### 6. Check the numbers land in your folder

`<data folder>/grafana` and `<data folder>/prometheus` must both hold files.
If they are empty, the container keeps its data elsewhere and loses it on an
update: check the two `-v` lines of the data folder, and, with Colima, that
the folder is inside your home folder.

## The numbers and their labels

Seven settings make Claude Code send its numbers. `OTEL_RESOURCE_ATTRIBUTES`
names who sends them: the three `qf.` labels the dashboard filters by.

```
CLAUDE_CODE_ENABLE_TELEMETRY=1
OTEL_METRICS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_METRIC_EXPORT_INTERVAL=10000
OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative
OTEL_RESOURCE_ATTRIBUTES=qf.scope=product,qf.product=<product name>,qf.session=<side>
```

Only numbers are sent: cost, tokens, model, and the session's id. No prompt,
no answer, no file.

`qf.scope` is `product` for a product's sessions and `framework` for the
framework's own development; `qf.session` names the side: `developer` or
`watcher`. Where each set of lines goes depends on your role: its guide says.
Every place is a file, read by each session when it starts, never a
terminal's own settings, so it does not matter which tab started it. In
Prometheus the labels' dots become underscores: `qf_scope`, `qf_product`,
`qf_session`.

The sessions the framework starts add three labels of their own: `qf_kind`
(clarify, tester, coder, reviewer, describe_tests, describe_design,
expect_cases), `qf_stage` (the stage it works for, as in
`agent/stages.yaml`) and, for the watcher's sessions, `qf_pr` (the pull
request).

## The cost of a stage

Prometheus keeps 15 days; a stage can run longer. So every session the
framework starts keeps what it cost in a ledger of its own, one row when it
ends, kept for the whole project: `<data folder>/costs/costs.sqlite`, a SQLite
file, one per computer for every product. Grafana reads it through the SQLite
data source the container installs (`frser-sqlite-datasource`, step 4) and
shows it in the section **Cost of a stage**, over the whole project:

| Panel | Shows |
|---|---|
| Cost by stage · Total | What each stage's sessions cost, from the first to the last; the orchestrator beside the total |
| Effort by LLM | Sessions, hours and cost per LLM: sessions and hours compare every LLM, cost only those that report it |
| Cost by kind · split by LLM | clarify, tester, coder, reviewer, describe and expect sessions, and the orchestrator, each split by the LLM that ran it |
| Cost by pull request · split by stage | Each pull request, or its branch before it existed, split by stage, the most expensive first |

Switch it on with one line, the folder mounted at `/data/costs`:

```
QF_COSTS_DIR=<data folder>/costs
```

in the two `.env` files: the product's, and `~/.aspice_agent_secrets/.env`.
The user who runs the sessions must be able to write that folder.

- **The sessions the framework starts** write their row when they end: its
  pull request (the reviewer's side) or branch (the author's, before the pull
  request exists), stage, kind, the program that ran it, how long, tokens and
  cost. The cost comes from the session's own answer, so each Claude command
  in the `.env` files needs `--output-format json` (QUICKSTART step 8); the
  framework reads the answer as text and keeps the cost. Another LLM's
  session, or one stopped at its time limit, still gets its row, without
  cost.
- **Your own session, the orchestrator,** has no stage: the status line
  (*Your plan's allowance*) keeps one row per session in a product's folder,
  its cost the running total. It finds the folder in the same two `.env`
  files. Without the status line, its cost is missing.

**Check that rows arrive.** Give the agent one prompt in the product's folder,
then, in that folder:

```sh
python3 -c "import sqlite3, sys; from pathlib import Path; sys.path.insert(0, '.framework'); from tools.write_cost_ledger_tool import LEDGER, costs_folder; f = costs_folder(Path('.')); print(sqlite3.connect(Path(f) / LEDGER).execute('SELECT time, product, kind, stage, cost_usd FROM sessions ORDER BY time DESC LIMIT 5').fetchall() if f else 'QF_COSTS_DIR not set')"
```

(`python` where `python3` is missing.) The newest row is your session's:
kind `orchestrator`, your product's name. No row: the status line names why,
`cost not recorded: <reason>` (*When something goes wrong*). The sessions the
framework starts add theirs when they end.

## Your plan's allowance

On a Pro, Max or Ultra plan the dollars are list prices, not what you pay:
what limits you is the plan's allowance, a 5-hour window and a weekly one.
Claude Code tells a status line how much of each is used; it does not send it
with the numbers above. The status line `plan_usage_statusline.py` of this
folder shows it in your terminal, e.g. `5h 42 % (21:10) · week 18 % (Sat 09:00)`,
and sends it to the stack as `qf_plan_used_percent` and `qf_plan_resets_at`,
for the *5-hour window* section. In a product's folder it also keeps your
session's cost in the ledger as the orchestrator's row (*The cost of a stage*),
and where it cannot, it says why: `cost not recorded: QF_COSTS_DIR not set`.
Your role's guide says which settings file holds it. A status line you
already have is replaced: keep one of the two. The allowance is your
account's, so one tab with this status line counts every session, the
watcher's too. It is sent while
a tab works, at most every 10 seconds; between two sends the panels keep the
last value, and show 0 % once the window has reset.

In the 5-hour window section, *Cost by session* and *Cost by model* show each
one's share of the window, not dollars: its list-price dollars since the window
started, divided by what 1 % of the window costs (the dollars of every session
since it started, divided by the % used). The bars of every session add up to
*5-hour window used*. It is an estimate, since the allowance is not set in
dollars, and moves a lot while the window is nearly empty. Without the status
line the section stays empty: it needs to know when the window started.

## Every day

The container starts with the container runtime. On macOS with Colima, start
it after each boot: `colima start`. Docker Desktop starts it on its own when
set to start at sign-in. Then http://localhost:3000/d/claude-costs.

Sessions started while the stack is down still work; their numbers for that
time are lost. A session started without the settings is not counted.

## Changing the dashboard

The dashboard is generated: never edit it in Grafana, the change is not saved
to the file. Change a panel in `make_dashboard.py` of the framework, then run
`python make_dashboard.py` in this folder (`python3` where `python` is
missing): it writes `claude-costs.json` again. Grafana reads the file again
every 30 seconds. A framework release brings the new file to every product.

## Why the numbers are exact

Claude Code sends each session's running total, and every session starts its
own. Prometheus's `increase()` drops a new total's first value, so short
sessions count less than they cost (about 5 % less, measured on a working
day). Every panel counts instead what each session reached in the window
minus what it had before it, nothing for a session that started inside it:

```
max_over_time(cost[W]) - (last_over_time(cost[2d] offset W) or max_over_time(cost[W]) * 0)
```

## Limits

- **Claude Code only.** The dashboard reads `claude_code_cost_usage_USD_total`
  and `claude_code_token_usage_tokens_total`. Another LLM command line that
  sends OpenTelemetry numbers reaches the same stack under its own names and
  needs panels of its own; one that sends none is not counted.
- **Dollars are API list prices.** On a subscription they compare tabs, days
  and models; they are not what you are billed. *Your plan's allowance* shows
  what you are limited by.
- **Your own session has no stage.** Its labels are set when it starts, so
  it stays one tab, and the ledger keeps it as one orchestrator row; only the
  sessions the framework starts carry their kind, stage and pull request.
- **The ledger's cost needs the LLM to report it.** Claude does with
  `--output-format json`; another LLM's rows count sessions and hours only.
- **One computer.** Each computer sends to its own stack. One stack for a
  whole team needs port 4317 open to the network and Grafana with sign-in:
  not covered here.

## Updating the stack

```sh
docker pull grafana/otel-lgtm:<version>
docker rm -f lgtm
```

Then step 4 again with the new tag. The data folder is untouched. A framework
bump needs nothing, unless its changelog names a new line for step 4: the
dashboard folder is mounted from `.framework`. A container created before
framework 5.4.0 has no ledger: create the costs folder (step 2), then
`docker rm -f lgtm` and step 4 again.

## Switching it off

- **One side:** remove the settings from its `.env`, or from the settings
  file of your own session (your role's guide).
- **The stack, for now:** `docker stop lgtm` (macOS with Colima: `colima
  stop`). Sessions keep working; their numbers for that time are lost.
- **For good:** `docker rm -f lgtm`. The numbers stay in `<data folder>` until
  you remove it.

## When something goes wrong

| What you see | Do |
|---|---|
| `Cannot connect to the Docker daemon` | Start the container runtime (`colima start`, or Docker Desktop) |
| Grafana does not open | `docker ps` must list `lgtm`; if not, `docker start lgtm`, then `docker logs lgtm` |
| No dashboard *Claude costs* | `docker logs lgtm 2>&1 \| grep -i provisioning`; check the two `.framework/monitoring` lines of step 4 and step 3 |
| Dashboard empty | A session sends numbers every 10 seconds while it works: send one prompt, wait 20 seconds. Still empty: that session started without the settings, or before the stack — start it again |
| Collector receives, Prometheus stays empty | The settings miss `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative`: Prometheus refuses the default |
| A session missing from *Cost by session* | Its settings were not read: an `.env` line misspelt, or the watcher not restarted after adding them |
| `cost not recorded: QF_COSTS_DIR not set` in the status line | Neither the product's `.env` nor `~/.aspice_agent_secrets/.env` has the line (*The cost of a stage*) |
| `cost not recorded: cannot write <folder>` | The user running Claude cannot write that folder, or it is not a folder: check its rights as that user |
| *Cost of a stage* empty, the status line shows no reason | No status line is set for the user running Claude (your role's guide), or no session has ended yet: run the check of *The cost of a stage* |
| `Not logged in` after `su` or `ssh` as another user | Claude keeps its sign-in in that user's keychain, which such a login does not unlock: `security unlock-keychain ~/Library/Keychains/login.keychain-db` in that terminal (macOS), then start Claude again |
| `port is already allocated` in step 4 | Another program uses 3000, 4317 or 4318 (`lsof -i :3000`; Windows: `netstat -ano \| findstr :3000`) |
| Numbers gone after an update | The data folder was not mounted, or (Colima) lies outside your home folder: step 6 |
