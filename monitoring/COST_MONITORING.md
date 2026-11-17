# Cost monitoring

An optional companion of the framework. It sets up a local Grafana that shows
what the LLM sessions of a product cost, now and today, per tab and per model.
Nothing in the framework needs it: no gate, tool or rule reads it, and a
product works the same without it.

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

Dashboard **Claude costs**, today so far by default:

| Area | Panel | Shows |
|---|---|---|
| Now | Spend rate, last 15 min | Dollars per minute over the last 15 minutes |
| Now | Sessions spending now | Sessions whose cost grew in the last 5 minutes |
| Now | By tab | Each tab's cost in the last 15 minutes and today |
| Today | Cost today | Every session in the filter |
| Today | Of the daily limit | Cost today against the daily limit: orange from 80 %, red from 100 % |
| Today | Cost by model | Dollars per model |
| Today | Cost per hour | One bar per hour, stacked by tab |
| Today | Tokens today by type | input, output, cacheRead, cacheCreation |
| Today | Cost today by tab | One bar per tab, each tab in its colour of *Cost per hour* |

At the top: **Scope** and **Product** filter every panel; **Daily limit ($)**,
50 by default, is a text box — type a new value for this view. The limit only
colours the panel; nothing is stopped.

A **tab** is what one setting of `qf.session` labels: `developer` for your own
tab and the sessions the framework starts for it (clarify, tester, coder),
`watcher` for the reviewer and describe sessions of the watcher.

## One-time setup

Each computer that runs sessions gets its own stack. The commands use three
placeholders:

- `<data folder>`: where the numbers are kept, outside the container, e.g.
  `~/qf-monitoring` (Windows: `C:\qf-monitoring`). Removing or updating the
  container keeps them.
- `<product>`: the product's folder, which holds `.framework`.
- `<product name>`: the product's name as the dashboard shows it, e.g.
  `wp_publisher`.

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
mkdir -p <data folder>/grafana <data folder>/prometheus
```

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force <data folder>\grafana, <data folder>\prometheus
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
  -e GF_PATHS_DATA=/data/grafana \
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
  -e GF_PATHS_DATA=/data/grafana `
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

## Switching the numbers on

Seven settings make Claude Code send its numbers. `OTEL_RESOURCE_ATTRIBUTES`
names who sends them: the three `qf.` labels the dashboard filters by.

```
CLAUDE_CODE_ENABLE_TELEMETRY=1
OTEL_METRICS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_METRIC_EXPORT_INTERVAL=10000
OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative
OTEL_RESOURCE_ATTRIBUTES=qf.scope=product,qf.product=<product name>,qf.session=<tab>
```

Only numbers are sent: cost, tokens, model, and the session's id. No prompt,
no answer, no file.

Put them where each session reads its settings — the same `.env` files that
name the commands of the independent sessions (QUICKSTART step 8):

| Where | `<tab>` | Counts |
|---|---|---|
| The product's `.env` | `developer` | The sessions the framework starts for you: clarify, tester, coder |
| `~/.aspice_agent_secrets/.env` | `watcher` | The reviewer and describe sessions the watcher starts |
| Your own tab, before starting the agent | `developer` | Your own session, which no `.env` reaches |

For your own tab, the same lines as `export` (macOS, Linux):

```sh
export CLAUDE_CODE_ENABLE_TELEMETRY=1 OTEL_METRICS_EXPORTER=otlp \
  OTEL_EXPORTER_OTLP_PROTOCOL=grpc OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
  OTEL_METRIC_EXPORT_INTERVAL=10000 OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative \
  OTEL_RESOURCE_ATTRIBUTES=qf.scope=product,qf.product=<product name>,qf.session=developer
```

Windows (PowerShell), one line each:

```powershell
$env:CLAUDE_CODE_ENABLE_TELEMETRY = "1"
$env:OTEL_METRICS_EXPORTER = "otlp"
$env:OTEL_EXPORTER_OTLP_PROTOCOL = "grpc"
$env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317"
$env:OTEL_METRIC_EXPORT_INTERVAL = "10000"
$env:OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE = "cumulative"
$env:OTEL_RESOURCE_ATTRIBUTES = "qf.scope=product,qf.product=<product name>,qf.session=developer"
```

A watcher reads its `.env` when it starts: restart it once after adding the
lines. In Prometheus the labels' dots become underscores: `qf_scope`,
`qf_product`, `qf_session`.

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
  and models; they are not what you are billed.
- **Per tab, not per pull request or stage.** The sessions the framework
  starts carry the label of the `.env` that starts them. Labels per pull
  request, stage and kind of session come with a later framework release.
- **One computer.** Each computer sends to its own stack. One stack for a
  whole team needs port 4317 open to the network and Grafana with sign-in:
  not covered here.

## Updating the stack

```sh
docker pull grafana/otel-lgtm:<version>
docker rm -f lgtm
```

Then step 4 again with the new tag. The data folder is untouched. A framework
bump needs nothing: the dashboard folder is mounted from `.framework`.

## Switching it off

- **One session or tab:** remove the settings from its `.env`, or open the
  tab without the `export` line.
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
| A tab missing from *By tab* | Its settings were not read: an `.env` line misspelt, or the watcher not restarted after adding them |
| `port is already allocated` in step 4 | Another program uses 3000, 4317 or 4318 (`lsof -i :3000`; Windows: `netstat -ano \| findstr :3000`) |
| Numbers gone after an update | The data folder was not mounted, or (Colima) lies outside your home folder: step 6 |
