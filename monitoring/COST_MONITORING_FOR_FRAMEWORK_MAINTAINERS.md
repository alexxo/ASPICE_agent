# Cost monitoring for framework maintainers

**For:** you develop the framework, in its own repository, and on the same
computer you run a product built with it, to try each release as a product
team would. The product runs as a second user of the computer, the developer
user, so it has its own home folder, secrets and sign-ins, as a product
team's computer would. One stack shows both: the framework's own sessions
and the product's.

**Not for:** a product team. Their setup has one user and no framework
repository: [`COST_MONITORING_FOR_PRODUCT_DEVELOPERS.md`](COST_MONITORING_FOR_PRODUCT_DEVELOPERS.md).

What the stack is, what it shows and what to do when something goes wrong
are in [`COST_MONITORING_COMMON_STACK.md`](COST_MONITORING_COMMON_STACK.md).
This guide says only what differs. The commands are for macOS, where this
setup runs; on Linux, `ssh` and the folder rights work the same way, with
the group commands of your distribution.

## Placeholders

| Placeholder | Means | e.g. |
|---|---|---|
| `<maintainer>` | your own user, who develops the framework and runs the stack | `maintainer` |
| `<developer user>` | the second user, who runs the product's agent and watcher | `developer` |
| `<framework repo>` | your clone of the framework's repository | `~/work/ASPICE_agent` |
| `<product>` | the product's folder, owned by `<developer user>` | `~/work/my_product` |
| `<product name>` | the product's repository name | `Team_repo_my_product` |
| `<owner>` | the GitHub owner whose reviewer token the watcher uses (QUICKSTART step 9) | `my-org` |
| `<data folder>` | the stack's data, inside `<maintainer>`'s home, writable by both users | `~/qf-monitoring` |

## Who runs what

| What | User | Reads its settings from |
|---|---|---|
| The stack (Colima, the `lgtm` container) | `<maintainer>` | the `docker run` command of step 3 |
| Your session on the framework | `<maintainer>` | `<maintainer>`'s shell profile (its numbers), `<framework repo>/.claude/settings.local.json` (its status line) |
| The product's agent, the orchestrator | `<developer user>` | `<developer user>`'s shell profile, `<product>/.claude/settings.local.json`, the product's `.env` |
| The sessions the agent starts | `<developer user>` | the product's `.env` |
| The watcher and its sessions | `<developer user>` | `~/.aspice_agent_secrets/.env` of `<developer user>` |

Each user's terminals are opened from your desktop with `ssh`, so both work
side by side without switching the computer's user.

## One-time setup

### 1. Remote login for the developer user

System Settings › General › Sharing › **Remote Login** on. Click (i) next to
it, choose *Allow access for: Only these users*, and add `<developer user>`.
Then, as `<maintainer>`:

```sh
ssh <developer user>@localhost whoami
```

It prints `<developer user>`.

### 2. The data folder, shared

As `<maintainer>`, create it as in the common stack, step 2, and let the
developer user write it: the ledger is written by that user's sessions, read
by the container you run.

```sh
mkdir -p <data folder>/grafana <data folder>/prometheus <data folder>/costs
chmod +a "group:staff allow list,add_file,search,add_subdirectory,delete_child,readattr,writeattr,readextattr,writeextattr,readsecurity,file_inherit,directory_inherit" <data folder>/costs
```

Both users must be in the group `staff` (every standard macOS user is). The
rule is inherited: the ledger file, created later by either user, stays
writable by both. Check as `<developer user>`:

```sh
ssh <developer user>@localhost "touch <data folder>/costs/.check && rm <data folder>/costs/.check && echo writable"
```

### 3. The stack, with the dashboard from the framework repository

The common stack, steps 1 and 3 to 6, as `<maintainer>`, with one change in
step 4: the three lines that mount `<product>/.framework/monitoring` mount
`<framework repo>/monitoring` instead, so the dashboard you change shows at
once, not only once the product moves to a new release:

```sh
  -v "<framework repo>/monitoring:/otel-lgtm/claude-dashboards:ro" \
  -v "<framework repo>/monitoring/provider.yaml:/otel-lgtm/grafana/conf/provisioning/dashboards/claude-costs.yaml:ro" \
  -v "<framework repo>/monitoring/costs_datasource.yaml:/otel-lgtm/grafana/conf/provisioning/datasources/costs.yaml:ro" \
```

### 4. The product, as the developer user

As `<developer user>`, follow
[`COST_MONITORING_FOR_PRODUCT_DEVELOPERS.md`](COST_MONITORING_FOR_PRODUCT_DEVELOPERS.md),
steps 2 to 4, with `QF_COSTS_DIR=<data folder>/costs`: the shared folder.
Skip its step 1: the stack is yours.

### 5. Your own session on the framework

As `<maintainer>`, add the telemetry lines to your shell profile
(`~/.zshrc`): Claude Code ignores them in a repository's `.claude/` files,
as the product developers' step 3 says.

```sh
# ~/.zshrc — Claude Code telemetry for my own session (cost monitoring)
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_METRIC_EXPORT_INTERVAL=10000
export OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative
export OTEL_RESOURCE_ATTRIBUTES=qf.scope=framework,qf.session=developer
```

Then write `<framework repo>/.claude/settings.local.json` (git ignores it):

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 <framework repo>/monitoring/plan_usage_statusline.py"
  }
}
```

Open a new terminal and start Claude in `<framework repo>`.

`qf.scope=framework` keeps your costs apart: the dashboard shows them as
*framework · orchestrator*, and the **Scope** filter picks either side. They
reach the live sections only: the framework's repository has no `qf.yaml`
and no stages, so the ledger, *Cost of a stage*, holds the product's
sessions alone.

The allowance in the *5-hour window* section is the account's of whichever
tab sent it last. Sign both users into the same Claude account, or the
panel mixes two allowances.

### 6. Only if the developer user keeps being signed out

Over `ssh`, Claude takes the developer user's sign-in from that user's
keychain, which `ssh` does not unlock: every day's step 3 unlocks it. It
locks again on its own (after a while, when the computer sleeps). If that
keeps stopping the sessions, a token needs no keychain: as
`<developer user>`, run `claude setup-token` (easiest from that user's own
desktop: it opens a browser), then add `CLAUDE_CODE_OAUTH_TOKEN=<the token>`
with an editor to `~/.aspice_agent_secrets/.env` and to the product's `.env`,
and restart the watcher.

## Every day

One terminal window, one tab per row (⌘T opens the next):

| Tab | User | Paste |
|---|---|---|
| 1 · awake | `<maintainer>` | `colima start && docker start lgtm; caffeinate -dims` — leave it running |
| 2 · framework | `<maintainer>` | `cd <framework repo> && claude` |
| 3 · product | `<developer user>` | `ssh <developer user>@localhost`, then `security unlock-keychain ~/Library/Keychains/login.keychain-db`, then `cd <product> && claude` |
| 4 · watcher | `<developer user>` | `ssh <developer user>@localhost`, then `security unlock-keychain ~/Library/Keychains/login.keychain-db`, then `cd <product>` and the watcher's command of QUICKSTART step 9, with `<owner>` |

Each `ssh` tab unlocks the keychain itself: an unlock in another tab does not
reach it. At the end of the day: Ctrl+C in tabs 4 and 1, `/exit` in tabs 2
and 3, then `colima stop`.

Check once after the first prompts: Grafana shows both scopes, and the
check of *The cost of a stage* (common stack), run in `<product>` as the
developer user, shows the product's newest rows.

## When something goes wrong

The common stack's table first. What only this setup meets:

| What you see | Do |
|---|---|
| `Not logged in` in tab 3 or 4 | That tab's keychain is locked: unlock it in that tab, start Claude or the watcher again. Keeps coming back: step 6 |
| `fatal: detected dubious ownership` when you run git on `<product>` as `<maintainer>` | The product is the developer user's: run git there as that user (tab 3). Do not add a `safe.directory` exception |
| `cost not recorded: cannot write <folder>` in tab 3 | The data folder lacks the rule of step 2, or the ledger was created before it: run step 2's `chmod +a` on the ledger file as well |
| `zsh: command not found: python` over `ssh` | Write `python3` |
| An `ssh` tab froze after the computer slept | Close it, open it again; tab 1 keeps the computer awake |
| `!` in front of a command in a plain terminal | Leave it out: `!` is for Claude's prompt only; in zsh it inverts the exit code |
