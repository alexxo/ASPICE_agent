# Changelog

All notable changes to this Quality Framework are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The **top entry** is the current framework version. A product runs one version: its framework submodule is pinned at that version's release tag.

## Provenance convention

Every entry that originates outside the maintainer carries an **Origin** line, so a change can be traced back to what caused it years later:

- `Origin: FB-nnn (<product>)` — a product's `FRAMEWORK_FEEDBACK.md` entry. The reporting channel is `skills/sup/report_framework_feedback_skill/SKILL.md`.
- `Origin: found verifying FB-nnn` — surfaced while confirming another report, not itself reported. Historically the highest-yield category: the framework's own blind spots cluster around the ones a product happened to notice.
- `Origin: internal` — found by the framework's own suite or maintainer.

Reports predating the `FB-nnn` template (v2.0.0 and earlier) are cited as `Origin: product report, <date>`. Their record lives in the release entry that answered them.

**Defect classes** (shared with `templates/FRAMEWORK_FEEDBACK.md`): **C1** silent bypass · **C2** false claim · **C3** unimplemented policy · **C4** contract defect · **C5** missing capability · **C6** friction/docs. C1 and C3 are the framework's worst failures — a gate that reports success without checking, and a declared gate with nothing behind it.

## Migration convention

Every version carries a **Migration** table directly under its heading: the exact edit, where it goes, and whether it is required. `required` means the build fails until it is done. Nothing else in the entry is a migration instruction — if it is not in that table, no action is needed.

## Scope of this file

**This file records what actually changed between releases, and nothing else.**
Every entry is past tense, describes work that shipped in that version, and is
never edited once released.

Nothing here describes work that has not been done. No open items, no planned
improvements, no deferred decisions — a release entry is a permanent statement
about that release, not a status board, and a reader can trust it without
checking whether it is still current.

---

## [Unreleased]

## [5.4.7] - 2026-11-21

A changed test that keeps its checks may pass on built code, also when its commit removes another test from the file.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required |

### Fixed

- **A changed test that kept its checks was refused when its commit removed another test** (`gates/swe/verify_test_first_gate.py`). Once a commit removed a test from a file of built units, every passing test of that file was reported as passing "before its code exists", so the FB-85 rule never applied there and right code could never pass. Now only a new test in such a commit is refused, as `enforce_test_first_skill` R4 states, with its own message; a test the file already had is a changed test, and passes when it keeps every check of its first version. Origin: FB-95 (wp_publisher).

## [5.4.6] - 2026-11-21

A component that runs where the product does not control it, like a frontend in the visitor's browser, makes its calls into the product a trust boundary with required security tests; an interface names security templates exactly when it crosses a trust boundary.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required |
| Add `runs_in: untrusted` to every component block of a component that runs where the product does not control it (a browser frontend, a mobile app), and give each interface between it and a component that does not run untrusted the `security_templates` its threats need | the product's `docs/architecture/` | required where such a component exists — `MISSING_SECURITY_TEMPLATES` otherwise, once it is marked |
| Remove `security_templates` from every interface crossing no trust boundary: between two external actors, or between two components that both run where the product controls them (or both untrusted) | the product's `docs/architecture/` | required — `TEMPLATES_WITHOUT_BOUNDARY` otherwise |

### Fixed

- **A browser frontend's calls to its backend needed no security tests** (`contracts/component_contract.v1.schema.json`, `gates/swe/verify_security_tests_gate.py`, `gates/swe/check_design_contract_gate.py`). The frontend is a component of the product, so its interfaces are internal, and only an external interface's templates were required — yet anyone can call what the browser calls. A component now says `runs_in: untrusted`; the product's end of an interface whose other end is external, or runs untrusted while it does not, crosses a trust boundary and needs a passing `@security` test per template. `create_security_tests_skill` R1, R3; `write_design_skill`; `derive_architecture_plugin` steps 4 and 6; Quality doc principle #16, § 5 stages 5 and 6 rules 24, 25 and 28; Appendix A.5 *Trust boundaries inside the product*. Origin: FB-9 (TBO-STUDIO).
- **An edge between two external actors had to name templates no gate could require** (`contracts/interface_contract.v1.schema.json`, `gates/swe/check_design_contract_gate.py`). The schema required `security_templates` whenever `external` was true, though no end was the product's. The schema no longer requires them; `check_design_contract_gate`, which sees the ends, reports an interface crossing a trust boundary without templates (`MISSING_SECURITY_TEMPLATES`) and one naming templates across none (`TEMPLATES_WITHOUT_BOUNDARY`). Origin: FB-10 (TBO-STUDIO).

## [5.4.5] - 2026-11-21

Your own session's cost monitoring settings go in your shell profile: Claude Code ignores them in a product's `.claude/` files, where 5.4.3 put them.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the seven telemetry lines (`CLAUDE_CODE_ENABLE_TELEMETRY`, `OTEL_…`) out of the `env` block of `<product>/.claude/settings.local.json` into your shell profile as `export` lines (`~/.zshrc`, `~/.bashrc`; Windows: `$PROFILE` with `$env:`), as in `COST_MONITORING_FOR_PRODUCT_DEVELOPERS.md` step 3; keep `statusLine` in `settings.local.json`; open a new terminal and start Claude again | the developer's computer | optional — only with cost monitoring, and needed there: without it your own session sends nothing |

### Fixed

- **Your own session sent no numbers** (`monitoring/COST_MONITORING_FOR_PRODUCT_DEVELOPERS.md` step 3, `COST_MONITORING_FOR_FRAMEWORK_MAINTAINERS.md` step 5). 5.4.3 put its telemetry settings in the repository's `.claude/settings.local.json`, and Claude Code ignores telemetry settings in a repository's `.claude/` files. Before, they came only from lines typed into a tab, lost when it was restarted. The guides now put them in the shell profile, read by every new terminal; the sessions the framework starts inherit them and take their own labels from their `.env`. The status line stays in `settings.local.json`. QUICKSTART step 10; Quality doc § 5 *Cost monitoring, an optional companion*; Appendix A.1 *The own session's numbers from the shell profile*. Origin: found verifying the pilot's dashboard.

## [5.4.4] - 2026-11-20

A security scan counts only when the scanner finished; no session runs the person's own hooks, and an approval from a reviewer whose copy changed is withdrawn; a new product's first pull request passes its gates; a criterion settled through `also` is rechecked once.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required |
| Add `completed_exit_codes` to both scanner rows of `docs/architecture/stack.yaml`: the exits of a finished scan, with or without findings — `[0, 1]` for osv-scanner; for gitleaks add `--exit-code 3` to its `run` and write `[0, 3]`, since it also exits 1 on an error | the product's stack | required — the stack is invalid without it |
| Add `--settings '{"disableAllHooks":true}'` after `--setting-sources user` on every `QF_COMMAND_TO_START_*` line, as in QUICKSTART step 8 | the product's `.env` and `~/.aspice_agent_secrets/.env` | required with Claude Code |
| Remove a local adapter that guards the scanners' exits, once the scans pass without it | the product | optional |

### Fixed

- **A failed scan passed as clean** (`gates/sup/scan_security_gate.py`, `contracts/stack_contract.v2.schema.json`). The gate read any JSON object as the scan's report and never its exit: a scanner that crashed and left a clean SARIF, or wrote `{}`, passed. Each scanner row now names its `completed_exit_codes`; any other exit, or a report that is no SARIF 2.1.0 log whose runs name their tool, is `SCAN_NOT_RUN`. Quality doc § 5 stage 9 rule 8; Appendix A.8 *A scan counts only when it finished*. Origin: FB-7 (TBO-STUDIO).
- **Sessions ran the person's own hooks** (`QUICKSTART.md` step 8, `tools/watch_reviews_tool.py`). `--setting-sources user` loads the person's user settings, whose hooks run as shell commands outside the rights a line gives; a reviewer's copy changed after it approved, and the approval still counted. Every Claude line now turns hooks off, and when a reviewer's copy changed the watcher withdraws that session's approval with a later review requesting changes on the same head. Quality doc § 5 stage 9; Appendix A.8 *A session never runs the person's own hooks*. Origin: FB-8 (TBO-STUDIO).
- **A new product's first pull request failed two gates** (`agent/start_product.md`). The prescribed first commit named no issue (`MISSING_REQUIREMENT_TOKEN`), and no step recorded the framework release it pins (`UNACCOUNTED_FRAMEWORK_BUMP`). Before that commit the agent now adds `No findings for <release> (<commit>)` to the feedback log, or the entry it recorded for a weakness met during the setup, and the message names the issue that starts the product. Appendix A.13 *The first commit passes the gates of its pull request*. Origin: FB-1, FB-2 (TBO-STUDIO).
- **A criterion settled through `also` was asked about a third time** (`agent/record_answer_tool.py`). The one recheck after a rewrite was counted for a question's own criterion only, so the criteria under its `also` stayed unchecked after the recheck and `verify_requirements_approval_gate` reported `CRITERIA_NOT_CHECKED`. Every place a question settles now counts alike. Origin: FB-94 (wp_publisher).

## [5.4.3] - 2026-11-20

A stage check runs a gate that several stages list once, not once per stage; cost monitoring is set up from one guide per role, every setting in a file, and says when the ledger gets no row.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | optional |
| Move your own session's monitoring settings out of the terminal into `<product>/.claude/settings.local.json`: the seven `OTEL_…` lines under `env`, and the `statusLine` block, as in `COST_MONITORING_FOR_PRODUCT_DEVELOPERS.md` step 3; remove the `export` lines from your shell profile and the `statusLine` from `~/.claude/settings.json`; quit Claude and start it again | the developer's computer | optional — only with cost monitoring |
| Make sure `QF_COSTS_DIR` is in the product's `.env` or `~/.aspice_agent_secrets/.env`: your own session's row now reads it there | the product's `.env` | optional — only with the cost ledger |

### Changed

- **A shared gate ran once per stage that lists it** (`agent/resolve_stage_tool.py`, `agent/run_gates_tool.py`). The walk checks every stage reached, and three gates are listed by several: `verify_test_first_gate` by 4, `check_verification_plan_gate` and `check_time_budget_gate` by 3; one check ran each again on the same tree. A gate is given only the product, so its result is the same in every stage: the walk now keeps each gate's result for the length of one check, and `run_gates` runs only the gates whose result it is not given. Measured on the framework's journey tests: 135 of 1634 gate runs fewer, 15 % of gate time. Nothing is kept after the check. Quality doc § 5 *What CI fails on*. Origin: internal.
- **One cost monitoring guide per role** (`monitoring/`). `COST_MONITORING.md` became `COST_MONITORING_COMMON_STACK.md`, the stack every setup shares, beside `COST_MONITORING_FOR_PRODUCT_DEVELOPERS.md` (one user of the computer, numbered steps, the status line one of them) and `COST_MONITORING_FOR_FRAMEWORK_MAINTAINERS.md` (a product run as a second user on the framework's computer, with placeholders). Each says whom it is for and whom not. QUICKSTART step 8 says one user runs a developer's clone, agent, watcher and secrets, and how to sign in as it. Quality doc § 5 *Cost monitoring, an optional companion*; Appendix A.1 *Cost monitoring set up by role, every setting in a file*. Origin: found verifying the pilot's empty ledger.

### Fixed

- **The orchestrator's ledger row needed a setting only one terminal had** (`monitoring/plan_usage_statusline.py`, `tools/write_cost_ledger_tool.py`). The status line read `QF_COSTS_DIR` from its own environment only, which a terminal reads when it opens: set later, or in another tab, the row was never written, and nothing said so. It now reads the setting where the sessions read it, the product's `.env` and `~/.aspice_agent_secrets/.env`, then the environment; where the row cannot be written, the status line shows `cost not recorded: <reason>`. The guide ends with a check that a row arrived, and QUICKSTART step 10 closes only once the agent finds its own session's row. Origin: found verifying the pilot's empty ledger.

## [5.4.2] - 2026-11-19

The clarify session is told which files it may read, and an answer that is no list of questions fails instead of passing as done.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release, then start the clarify session again | the product | required — a product whose requirements are under a folder (the setup's `docs/`) cannot end stage 2 without it |

### Fixed

- **The clarify session found no file** (`tools/start_session_tool.py`). Its prompt named none, a session started with the read-only command line can read files but not list a folder, and the setup puts them under `docs/`: the session guessed names, found nothing and answered in prose, and the launcher exited 0. The prompt now names every file the folder holds, as the describe sessions' prompts do, for any LLM and any layout; the launcher exits 1 when the answer is no list of questions (an empty list is one), naming the problem in its report. Quality doc § 3 *Independent sessions* rule 3, § 5 stages 1 and 2 rule 27; Appendix A.2 *The clarify session is told its files*. Origin: FB-93 (wp_publisher).

## [5.4.1] - 2026-11-19

A review on a pull request no longer runs the suites again on a head they already checked.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | optional |
| Copy the two steps *Restore the runs kept for this commit* and *Keep the runs for this commit* from `templates/github/quality_gates.yml`, where the template has them | `.github/workflows/quality_gates.yml` | optional — without them every review runs the suites again |

### Fixed

- **A review reran the whole workflow** (`templates/github/quality_gates.yml`). Every review on a pull request — an approval, changes requested, a dismissal — ran every suite again on a head already checked: in wp_publisher 121 such runs in five weeks, 143 of its 423 CI minutes (34 %). The workflow now keeps the runs of `.qf/runs` for the commit (`actions/cache`, keyed by the commit alone) and restores them before the report: every gate still runs and decides, the suites do not run twice; a new commit, and the main branch's own merge commit, run everything afresh. Quality doc § 5 unit stages rule 13; Appendix A.8 *A review does not run the suites again*. Origin: FB-92 (wp_publisher).

## [5.4.0] - 2026-11-19

The cost of a stage over the whole project: every session the framework starts, and your own, keeps what it cost in a ledger the dashboard reads, by stage, kind of session, LLM and pull request.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | optional — only the cost monitoring changed |
| Add `--output-format json` to every Claude command line (`QF_COMMAND_TO_START_…`), as in QUICKSTART step 8 | the product's `.env` and `~/.aspice_agent_secrets/.env` | optional — without it a session's ledger row has no cost |
| Add `QF_COSTS_DIR=<data folder>/costs` to both `.env` files, and `export QF_COSTS_DIR=<data folder>/costs` to your own tab's lines (`COST_MONITORING.md`, *The cost of a stage*); restart the watcher | the product's `.env`, `~/.aspice_agent_secrets/.env`, your tab | optional — without it no ledger is written |
| Set `qf.product` in `OTEL_RESOURCE_ATTRIBUTES` to the product's repository name, e.g. `Team_repo_wp_publisher` | both `.env` files and your tab | optional — the Product filter then picks the same product in every section |
| Create `<data folder>/costs`, then `docker rm -f lgtm` and step 4 of `COST_MONITORING.md` again: three new lines mount the ledger and its data source and install the SQLite plugin | the computer running the stack | optional — without it the section *Cost of a stage* stays empty |
| Use the status line `plan_usage_statusline.py` (`COST_MONITORING.md`, *Your plan's allowance*) | `~/.claude/settings.json` | optional — without it your own session, the orchestrator, is not in the ledger |

### Added

- **The cost ledger** (`tools/write_cost_ledger_tool.py`). Every session the framework starts adds one row when it ends to `<QF_COSTS_DIR>/costs.sqlite`, one file per computer: its pull request (the reviewer's side) or branch (the author's), stage, kind, the program that ran it, how long, tokens and cost. The cost comes from Claude's result object (`--output-format json`); the framework reads only its answer, as if the command had printed text, so every reader of a session's output stays as it was, and another LLM's output is read as it is, its row without cost. The status line keeps your own session as the orchestrator's row, its cost the running total. Quality doc *Cost monitoring, an optional companion*; Appendix A.1 *The cost of a stage, from its first session to its last*. Origin: internal (Alex).
- **Labels per session.** The sessions the framework starts add `qf.kind`, `qf.stage` and, on the watcher's side, `qf.pr` to the telemetry they send. Origin: internal (Alex).
- **Cost of a stage** (`monitoring/`). A fourth dashboard section over the whole project, read from the ledger through Grafana's SQLite data source (`frser-sqlite-datasource` 4.0.6, `costs_datasource.yaml`): *Cost by stage* with the project's *Total*, *Effort by LLM* (sessions, hours, cost), *Cost by kind* and *Cost by pull request · split by stage*, and a *Pull request* filter. Origin: internal (Alex).

### Changed

- **Sessions by kind in the live sections.** *Cost by tab* is *Cost by session*, *Cost over time by tab* is *Cost over time by session*: each kind of session, your own as the orchestrator. Every name the dashboard colours — kind, stage, LLM, model family, token type — has its own colour in every chart. Origin: internal (Alex).
- **The plan's window panels** fill their row, so *Tokens by type* no longer floats between two rows, and show their values only, sized by the panel. Origin: internal (Alex).

### Fixed

- **Telemetry is not optional** (Quality doc Appendix A.11): the FB-91 entry said a product may state observability as a requirement; every feature already has its observability requirement, events and watcher. Origin: found verifying FB-91.

## [5.3.0] - 2026-11-18

A framework feedback entry reaches the framework as an issue of its repository, a problem records the stage it got through, and anyone reports a problem with the product's problem form.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required — to file FB-91 below |
| File every entry still *open* or *reported* in `FRAMEWORK_FEEDBACK.md`, FB-91 first: show it with `python .framework/tools/file_framework_feedback_tool.py --entry FB-<n> --show`, and once the person approved, run it without `--show` | the product's feedback log | required — `check_framework_feedback_gate` fails with UNFILED_FEEDBACK_ENTRY |
| Sign `gh` in with the person's own login (`gh auth login`) or a classic token with `public_repo`: a fine-grained token cannot open an issue on another owner's repository | the person | required to file |
| Copy `templates/github/problem_report.yml` | `.github/ISSUE_TEMPLATE/problem_report.yml` | optional — without it a reporter writes the problem block by hand |
| Add `origin` and `escape` (`stage`, `why`) to every problem past *open* or named by a test | the product's problem issues | required — `check_problem_record_gate` fails with MISSING_ANALYSIS; wp_publisher has none |

### Added

- **Feedback filed as an issue** (`tools/file_framework_feedback_tool.py`). `--show` prints the repository (the framework's GitHub URL in `.gitmodules`), the title — the entry's, with the product's repository name — and the body, the full report; without it the tool opens the issue with the person's `gh` login and keeps in the log only Date, Framework version, Status (*reported*), Issue (its URL), Impact on this product and Workaround applied. The developer agent files only after the person approved the text and its publishing in the session; the framework answers in the issue and closes it with the fixing release. An entry is never filed twice. Quality doc § 5 stage 9 rule 9; Appendix A.8 *Feedback reaches the framework as an issue*. Origin: FB-91 (wp_publisher).
- **The problem form** (`templates/github/problem_report.yml`, copied by `tools/create_product_tool.py`). What happens, where, how to make it happen, what was expected and what happened instead, labelled *problem*: a defect found in operation is reported without an agent. The developer agent writes the problem block from the answers when it analyses it; an open report named by no test passes until then. Quality doc § 5 stage 12 rule 13. Origin: FB-91 (wp_publisher).

### Changed

- **Unfiled feedback fails** (`check_framework_feedback_gate`). An entry *open* or *reported* without its Issue is UNFILED_FEEDBACK_ENTRY; a filed entry needs only the product's part, its Issue an issue URL of the framework's repository. Entries in the full form still pass. Origin: FB-91 (wp_publisher).
- **Where a defect got through** (`problem.v1`, `check_problem_record_gate`). The analysis adds *origin*, the stage that brought the defect in, and *escape*, the *stage* that should have caught it and *why* it did not, both by their id in `agent/stages.yaml`. The release report counts the problems by the stage they got through. An escape that is the framework's weakness becomes a framework feedback entry naming the problem, checked by Review (`resolve_problems_skill` R11). Quality doc SUP.9 BP2, BP7; Appendix A.11 *Learning where a defect got through*. Origin: FB-91 (wp_publisher).

### Removed

- Three unit tests that ran the same lines as another and asserted the same outcome. Origin: internal (Alex).

## [5.2.0] - 2026-11-17

A later review round reviews what changed since the last one, an approval holds while nothing it read changed, and the cost dashboard shows the plan's allowance in three sections.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required — the watcher restarts itself from the new pin (v5.0.13) |
| To see the plan's allowance: add the status line of `.framework/monitoring/COST_MONITORING.md` *Your plan's allowance* to `~/.claude/settings.json` | the person | optional — only the dashboard's 5-hour window section needs it |

### Changed

- **A later round reviews from the last one** (`tools/watch_reviews_tool.py`, `agent/run_reviewer_agent.md`, `plugins/sup/derive_review_plugin/SKILL.md`). The watcher's prompt names the reviewer agent's last reviewed head and the files changed since (`git diff --name-only`); the reviewer reads those, what they touch and the fix of every open finding, the rest keeping its last judgement, and reviews the whole pull request again when the change is wide. The method asks for every finding in the round that finds it. Quality doc § 5 stage 9 rule 1; Appendix A.8 *A later round reviews what changed*. Origin: FB-90 (wp_publisher).
- **An approval holds while nothing it read changed** (`tools/watch_reviews_tool.py`). The expected cases of a requirement are kept under `.qf/reviews/described/` by the instructions, its statement and criteria, and the glossary, as the descriptions are; a round lists only the requirements with none kept. When since the approved head only the framework pin or the feedback log changed, and the pull request changes neither, the watcher posts the approval again on the new head, as the reviewer agent, with one line naming what changed. `tools/post_review_tool.py` takes the API address from its caller. Quality doc § 5 stage 9 rules 1 and 14; Appendix A.8 *An approval holds while nothing it read changed*. Origin: FB-89 (wp_publisher).
- **The cost dashboard in three sections** (`monitoring/`). *Now · last 15 min*, *5-hour window* and *Today*, each with Cost by tab, Cost by model and Tokens by type as horizontal bars from zero, every tab in one fixed colour; *5-hour window* adds 5-hour window used and Week used, with their reset times, and shows its costs as a share of the window; *Today* adds Cost over time by tab, one bar per hour standing on its start, so the hour running now has one. Each section keeps its own span, whatever the time picker says. Removed: the spend rate, sessions spending now, the cost and daily-limit stats, and the *Daily limit ($)* box. Origin: internal (Alex).

### Added

- **The plan's allowance** (`monitoring/plan_usage_statusline.py`). A Claude Code status line that shows how much of the 5-hour and the weekly allowance is used, e.g. `5h 42 % (21:10) · week 18 % (Sat 09:00)`, and sends both, with their reset times, to the monitoring stack as `qf_plan_used_percent` and `qf_plan_resets_at`. `COST_MONITORING.md` *Your plan's allowance*. Origin: internal (Alex).

## [5.1.2] - 2026-11-17

A tab keeps the colour it had before in both tab charts of the cost dashboard.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | optional — only the dashboard changed; Grafana reads it from `.framework` |

### Fixed

- **Tab colours** in *Cost per hour* and *Cost today by tab*: 5.1.1 coloured tabs by name, which gave them new colours. Each tab now has a fixed colour in both charts, the one it had before (`framework · developer` green, `product · developer` yellow, `product · watcher` blue); another tab takes the next colour of Grafana's order. Origin: internal (Alex).

## [5.1.1] - 2026-11-17

The cost dashboard shows each tab's cost today as bars.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | optional — only the dashboard changed; Grafana reads it from `.framework` |

### Added

- **Cost today by tab** in the dashboard *Claude costs*: one horizontal bar per tab. A tab has the same colour here and in *Cost per hour*, which now colours tabs by name. `COST_MONITORING.md` *What you get* lists it. Origin: internal (Alex).

## [5.1.0] - 2026-11-16

Cost monitoring, an optional companion: a guide and a Grafana dashboard that show what a product's LLM sessions cost, now and today.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required — the watcher restarts itself from the new pin |
| To see the costs: follow `.framework/monitoring/COST_MONITORING.md` (one container, the settings in the two `.env` files) | the person | optional — nothing depends on it |

### Added

- **Cost monitoring** (`monitoring/`). `COST_MONITORING.md` sets up a local Grafana for macOS, Linux and Windows: one pinned container (`grafana/otel-lgtm:0.41.0`), the numbers kept in a folder of the person's, and the settings that make Claude Code send its cost and tokens, in the two `.env` files that already reach every session the framework starts. The dashboard *Claude costs* (`claude-costs.json`, generated by `make_dashboard.py`) shows the spend rate, the sessions spending now, each tab's cost, cost today against a daily limit, by model, per hour, and tokens by type; it counts each session's highest value, not `increase()`, which drops a new session's first numbers. Grafana reads it from the product's `.framework`, so each release brings its dashboard. No gate, tool or rule uses it. QUICKSTART step 10 (optional); Quality doc § 5 *Cost monitoring, an optional companion*; Appendix A.1 *Cost monitoring ships with the framework, optional*.

## [5.0.14] - 2026-11-16

A usage limit in a describe session waits for the reset on its own, and a round describes only the tests and designs that changed.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required — the watcher restarts itself from the new pin (v5.0.13) |

### Fixed

- **A usage limit in a describe session stopped the review until the person typed R.** The review session's limit was already retried on its own; a describe session's was read as a broken answer. Every session's usage limit now gives the same stop: the watcher tries the head again every 10 minutes, one line each time, until the limit resets (`tools/watch_reviews_tool.py`). § 5 stage 9; Appendix A.8 *A usage limit in a describe session waits for the reset*. Origin: FB-87 (wp_publisher).
- **Every review round described every test again.** A test file's description, and a design's stories, are now kept by the instructions and the files' content under `.qf/reviews/described/`; a round describes only the files with no kept description, so an unchanged test costs no session and reads the same in every round (`tools/watch_reviews_tool.py`). § 5 stage 9; Appendix A.8 *A description is kept by the content it describes*. Origin: FB-88 (wp_publisher).

## [5.0.13] - 2026-11-15

The watcher follows a framework bump on its own: no person restarts it after a later bump.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required |
| Restart the watcher from the new pin (Ctrl+C, then QUICKSTART step 9) — the last time: from this release on it restarts itself | the person | required — the running watcher holds the old code, without the restart |

### Fixed

- **Every framework bump waited for the person at the keyboard.** The watcher kept the code it started with, and only the person, who holds the token, could start it again. After each look, when the framework's version on disk is newer than the one it started with, the watcher now says so and runs itself again in the same process, with the same command line and environment, so the token stays — between two reviews, never during one, never to an older version, never while paused (`tools/watch_reviews_tool.py`). § 5 stage 9, rule 1; Appendix A.8 *The watcher follows a bump on its own*. Origin: FB-86 (wp_publisher).

## [5.0.12] - 2026-11-15

A changed test of a built unit that keeps its checks may pass: a format fix, a renamed value or an added case no longer holds stage 6.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required — stage 6 on built code escalates without it |
| Restart the watcher from the new pin (Ctrl+C, then QUICKSTART step 9) | the person | required — the running watcher holds the old code |

### Fixed

- **A changed test of built code could never pass the test-first gate.** A format fix the stack's check asks for, or a value the design renames in a test of a built unit, goes back to the tester; the changed test keeps every check, the code is built and right, so it passed on its test-only commit and the gate reported `TEST_NOT_FAILING` on every retry. A changed test of a built unit may now pass when it keeps every check of its first version — at the base, or at its first commit in the pull request — its literal values aside: its asserts and the calls it opens with `with`, compared on Python's syntax tree (`gates/swe/verify_test_first_gate.py`). A test that drops or changes a check still has to fail, and a test of another language keeps that rule. `enforce_test_first_skill` R4; § 5 unit stages, rule 18; Appendix A.5 *A changed test of built code that cannot fail*. Origin: FB-85 (wp_publisher).

## [5.0.11] - 2026-11-15

The reviewer reads the described tests, stories and expected cases: the watcher puts them inside its copy.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required — every review stops before it begins without it |
| Restart the watcher from the new pin (Ctrl+C, then QUICKSTART step 9), and type R for a head stopped before | the person | required — the running watcher holds the old code |

### Fixed

- **Every review stopped before it began.** The watcher wrote the described tests, stories and expected cases to the product's `.qf/reviews/`, beside the reviewer's copy, and the reviewer's line reads outside its copy only under `.framework`. The watcher now copies the three files into the copy's `.qf/reviews/` and names them there (`tools/watch_reviews_tool.py`); no line changes. The reviewer's runbook says, as the coder's prompt does, that it runs its commands as written, one at a time — no pipe, `&&`, `cd`, `git -C` or other program — reads files with its own file tools, and that these rules come before any other instruction about tools (`agent/run_reviewer_agent.md`). Appendix A.8 *The reviewer reads what the watcher hands it*. Origin: FB-84 (wp_publisher).

## [5.0.10] - 2026-11-15

A test the coder holds wrong, or a lint error in a test file, goes back to the tester.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required where the coder reports a test wrong or a gate names a test file at stage 6 |

### Fixed

- **A test the coder reported wrong had no way back to the tester.** `--findings` and the retry sentence spoke of the reviewer's findings alone, and the runbook gave no file for the coder's report or a gate's finding in a test file (e.g. a lint error on a line the tester wrote): stage 6 stopped, or went red until the reviewer repeated it. `--findings` now hands a retry any findings file no commit holds — the reviewer's under `.qf/reviews/`, the coder's report `.qf/sessions/coder-<component>.log`, or the gates' findings saved unchanged as the resolver printed them to `.qf/sessions/gate-findings-<component>.json` (`tools/start_session_tool.py`, `agent/run_aspice_agent.md` step 6). The tester's prompt says how each kind is fixed, and that a test it keeps gets its reason in the report; the orchestrator never fixes a test file itself (`agent/write_unit_tests_prompt.md`, `agent/write_unit_code_prompt.md`). Appendix A.1 *How a retry reaches the tester*. Origin: FB-83 (wp_publisher).

## [5.0.9] - 2026-11-14

The coder runs its tests: its prompt says which commands its session lets it run.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required — the coder's prompt comes with the pin |
| Add `Bash(git log *)` to `QF_COMMAND_TO_START_CODER_SESSION` in the product's `.env`, after `Bash(git diff *)` (QUICKSTART step 8) | the person, on each machine | required with Claude Code; with another tool, allow `git log` as its flags say |

### Fixed

- **The coder's commands were refused without a word.** The coder's line allows a command by its start, one command at a time, and nothing told the coder: it ran pipes, `&&`, an interpreter's path, `git -C` and the reading tools the person's own instructions prescribe, and every one was refused — it wrote code it never ran, or stopped. The coder's prompt now says what passes: the plan's and the stack's commands as written, `git status`, `git diff` and `git log`, one command at a time, files read with the session's own file tools, and these rules before any other instruction about tools (`agent/write_unit_code_prompt.md`). The coder's line adds `git log` (QUICKSTART step 8); `tests/consistency/test_session_rights.py` keeps every git command of the prompt allowed. Appendix A.1 *The coder runs what its line allows*. Origin: FB-82 (wp_publisher).

## [5.0.8] - 2026-11-14

Stage 5 can come back to built code: a reviewer's missing case and a change request's new names pass the test-first gate.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required where a change request or a reviewer's finding brings stage 5 back after the code exists |

### Fixed

- **A missing case of built behaviour could never pass the test-first gate.** Every new test had to fail on its test-only commit, but a test the reviewer asks for, of behaviour the code already has, passes there. A new test of a file whose units are all built — by a commit of code without tests, earlier in the pull request or before it — now may pass: it guards the code. A changed test of a built unit still fails, or it was loosened, and so does a new one in a commit that removes a test from its file (`gates/swe/verify_test_first_gate.py`). Appendix A.5 *Stage 5 on built code*; § 5 unit stages, rule 18. Origin: FB-81 (wp_publisher).
- **A test file that could not be collected had no results.** A test importing a name the design adds to a built unit errors at collection, where pytest writes the module in the testcase's name and no classname; its error now belongs to that file and counts as red (`tools/read_test_results_tool.py`). § 5 unit stages, rule 15. Origin: FB-81 (wp_publisher).

## [5.0.7] - 2026-11-14

The stack's commands run in the product's own toolchain, and a retry hands the tester every open finding.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required where the machine's first Python lacks the product's stack, or a reviewer's finding is open over more than one round |
| Set the product's toolchain up as its stack says (e.g. a Python 3.12 environment with `requirements.txt` installed) and add `QF_PATH_TO_PRODUCT_TOOLCHAIN=<its bin folder>` to the product's `.env` (QUICKSTART step 2) | the person, on each machine | required where the machine's first Python lacks the product's stack — otherwise every red run of stage 5 fails `RED_RUN_WITHOUT_RESULTS` |

### Added

- **`QF_PATH_TO_PRODUCT_TOOLCHAIN`, the product's toolchain on the person's machine.** The framework ran the stack's commands on the `PATH` it was given, where the first Python is the one with the framework's runtime, not the product's language version and libraries: a product's unit suite found no `python`, or no `pytest`, and no test commit passed the test-first gate. The folders named in the product's `.env` now go first on the `PATH` of the stack's checks and suites (`tools/run_stack_commands_tool.py`) and of the coder's session, never of the framework's tools; unset, as in CI, nothing changes. A red run without results now quotes the command's last output line. QUICKSTART step 2; Appendix A.13 *The product's toolchain is the product's*. Origin: FB-80 (wp_publisher).

### Fixed

- **A retry got half the open findings.** A reviewer could carry an open finding into a later round by reference (*listed there*), and the tester's retry gets the latest round's file alone. The reviewer now restates every open finding in full in each round (`plugins/sup/derive_review_plugin/SKILL.md`, `agent/run_reviewer_agent.md`). The tester's and the coder's retry rule no longer narrows the work to the findings: it still follows the component's detailed design as it stands, and also fixes what the findings name (`agent/write_unit_tests_prompt.md`, `agent/write_unit_code_prompt.md`, the launcher's retry sentence). Appendix A.1 *How a retry reaches the tester*. Origin: FB-79 (wp_publisher).

## [5.0.6] - 2026-11-14

The reviewer's findings reach the tester and the coder on a retry.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required where a reviewer's finding on a component's tests or code is open |

### Fixed

- **A retry hands the tester the reviewer's findings.** The findings sit under `.qf/reviews/`, which git ignores; the tester's session runs in a copy of the committed head, and its prompt never mentioned findings, so a finding on the tests reached no one who may write them and the pull request could never be approved. `tools/start_session_tool.py --findings <file>` copies the findings file into the tester's folder and names it to the coder; `agent/write_unit_tests_prompt.md` and `agent/write_unit_code_prompt.md` fix exactly what it names, the tester giving the reason for a case it holds is not a test; `agent/run_aspice_agent.md` starts the retry with it. Design document *Independent sessions*, rule 3; Appendix A.1 *How a retry reaches the tester*. Origin: FB-78 (wp_publisher).

## [5.0.5] - 2026-11-14

The reviewer's runbook runs its token checks in the form its session line allows, so the reviewer agent reviews again.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release, then type `R` and Enter in the watcher to review the stopped heads again | the product | required — on 5.0.0 to 5.0.4 with the step-8 reviewer line, no pull request gets the reviewer agent's approval |
| Starting the reviewer by hand: give the session the reviewer agent's token in both `QF_HOST_TOKEN` and `GH_TOKEN`, as the watcher does | the person | required for a session started by hand |

### Fixed

- **The reviewer's session refused its own preconditions.** `agent/run_reviewer_agent.md` prefixed its `gh api` checks with `GH_TOKEN=$QF_HOST_TOKEN` and asked the session to test whether `QF_HOST_TOKEN` was set; the QUICKSTART step-8 line allows `gh api` by the start of the command, so every reviewer session stopped before reviewing. The watcher already gives the session the token as `GH_TOKEN`: the checks now run as plain `gh api …`, and the first, `gh api user -q .login`, stops unless `gh` acts as one of `review.agents`. A consistency test matches every `gh` command of the runbook against the step-8 line. Design document *Independent sessions*, rule 7; Appendix A.8 *How the reviewer's commands get its token*. Origin: FB-77 (wp_publisher).

## [5.0.4] - 2026-11-14

A change request's checkpoint 2 no longer turns the main branch red: the findings of its new requirements' work are reported until the stage that does that work is recorded again.

### Migration

| Edit | Where | Required |
|---|---|---|
| Move the framework pin to this release | the product | required where a change request's checkpoint 2 merged before its architecture — main turns green again |
| After the change's architecture merges, record stage 3 again: `python .framework/agent/record_stage_done_tool.py --stage architecture --root .` (the resolver asks for it) | the product | required — until then the findings naming the changed requirements stay reported |

### Fixed

- **A change request's new requirements wait for their architecture, not every pull request.** The merge of a change request's `checkpoint/2` made its new requirements part of the finished architecture stage at once; `check_design_contract_gate` found them met by no component and failed every later pull request, a framework bump too, until the change's architecture merged. Now the architecture follows the requirements as stages 4 to 7 do (`built_from_requirements` in `agent/stages.yaml`), and in a stage following the requirements a finding that names a requirement added or changed since the stage's latest record is reported, not failing, until the stage is recorded again — which needs its gates to pass. Every other finding of the stage stays enforced, and every finding while a release is proposed. `agent/resolve_stage_tool.py`, design document § 5 *What CI fails on*, Appendix A.4 *A change request's new requirements before its architecture*. Origin: FB-76 (wp_publisher).

## [5.0.3] - 2026-11-14

Python is whatever the machine has, `python` or `python3`; nothing new is installed.

### Migration

| Edit | Where | Required |
|---|---|---|
| Replace the session lines with those of QUICKSTART step 8 (`python3` allowed beside `python`) | both `.env` files | required where the machine's name is `python3` |
| Where the first Python on the `PATH` lacks PyYAML and jsonschema and another has them, put that one's folder first on the `PATH` in the shell profile of the user who runs the agent and the watcher | that user's shell profile | required on such a machine |
| A `.venv/` made for 5.0.2 and its `.gitignore` line can go | the product | optional |

### Changed

- **Python is whatever the machine has.** 5.0.2 asked for `python` and, where only `python3` existed, a virtual environment in the product — a second installation of a runtime the machine may already hold. Now QUICKSTART step 2 checks `python`, else `python3`, with the runtime; where the first on the `PATH` lacks it and another Python has it, the person puts that one first on the `PATH`. The runbooks run `python3` where `python` is missing, the session lines allow both names, and the setup no longer ignores `.venv/`. Origin: FB-75 (wp_publisher).

## [5.0.2] - 2026-11-14

QUICKSTART names one Python, `python`, as every command of the framework calls it.

### Migration

| Edit | Where | Required |
|---|---|---|
| Check `python -c 'import yaml, jsonschema'` in the terminals that start the agent and the watcher; where it fails, make the environment of QUICKSTART step 2 (`.venv/`) and activate it there | the product folder | required where `python` is missing or lacks the runtime |
| Add `.venv/` | the product's `.gitignore` | required with the environment |

### Fixed

- **One name for Python.** QUICKSTART step 2 checked `python3`, while the runbooks, the CI, the watcher, the upgrade's check and the sessions' command lines call `python`: on a machine with `python3` only, step 2 passed and every one of them failed. Step 2 now checks `python` with the runtime and, where the machine offers only `python3`, makes a virtual environment in the product, active in the terminals that start the agent and the watcher, whose sessions inherit it; the setup ignores `.venv/`. A consistency test keeps the guide on one name. Origin: FB-75 (wp_publisher).

## [5.0.1] - 2026-11-14

The command lines of the independent sessions give each session its rights and no more, and the upgrade to 5.x is a list of steps the product's agent can follow.

### Migration

| Edit | Where | Required |
|---|---|---|
| Follow "Upgrading an existing product" of `QUICKSTART.md`: the agent steps 1–4, the person steps 5–8 | the product, and the machine of the user who runs the watcher | required from 4.x; from 5.0.0, only the command lines below |
| Replace each command line with the lines of QUICKSTART step 8, one per session, each fallback the read-only line | both `.env` files | required — a bare agent command gives a session the rights of the user's own settings |

### Fixed

- **Each session's command gives its rights, no more.** 5.0.0 dropped the reviewer's allowed tools with the Claude Code commands and named no replacement: a bare command left a session the rights of the user's own settings — a reviewer allowed everything, or a tester and a coder unable to write. QUICKSTART step 8 now has a table of each session's rights (read, write, run) and the Claude Code lines that give them, checked against Claude Code 2.1: refusing everything not listed, the tester kept in its copy, the reviewer writing only its record. Each fallback is the read-only line, so a missing line stops a session, never widens it. A consistency test keeps the lines readable by the launcher and the reviewer's line in step with its runbook's tools. Origin: internal.
- **The upgrade, step by step.** "Upgrading an existing product" names who does what — the agent pins the framework and ignores `.env` through an issue and a pull request as every change, writes the command lines without a key and checks them without starting a session; the person adds keys, moves the token, writes `~/.aspice_agent_secrets/.env` with `chmod 600` and restarts the watcher, which then reviews the upgrade. Origin: internal.

## [5.0.0] - 2026-11-13

Every independent session runs on the LLM the person names, and the tester never sees the code: the tester and the coder work in sessions of their own, one component at a time, the tester in a copy of the product without its code.

### Migration

| Edit | Where | Required |
|---|---|---|
| Update the framework submodule to this release and commit the pin | the product | required |
| Write `QF_COMMAND_TO_START_AUTHOR_SESSIONS=<agent command with {prompt}>` and that LLM's key | the product's `.env` | required — clarify, the tester and the coder do not start without it |
| Add `.env` | the product's `.gitignore` | required — the keys must never be committed |
| `mkdir -p -m 700 ~/.aspice_agent_secrets && mv ~/.aspice_agent_reviewer_bot_token ~/.aspice_agent_secrets/reviewer_bot_github_token` | the machine of the user who runs the watcher | required |
| Write `QF_COMMAND_TO_START_REVIEW_SESSIONS=<agent command with {prompt}>` and that LLM's key | `~/.aspice_agent_secrets/.env` | required — the watcher does not start without it |
| Restart the watcher with the line of QUICKSTART step 9; drop `--command` | the watcher's terminal | required |

### Added

- **One launcher for the independent sessions.** `tools/start_session_tool.py` starts clarify, the tester and the coder; the watcher uses its settings for the reviewer and its three describe sessions. A session's command is its own setting, else its side's: the product's `.env` for the author's side (`QF_COMMAND_TO_START_CLARIFY_SESSION`, `…_TESTER_SESSION`, `…_CODER_SESSION`, else `QF_COMMAND_TO_START_AUTHOR_SESSIONS`), `~/.aspice_agent_secrets/.env` for the person's (`…_REVIEWER_SESSION`, `…_DESCRIBE_TESTS_SESSION`, `…_DESCRIBE_DESIGN_SESSION`, `…_EXPECT_CASES_SESSION`, else `QF_COMMAND_TO_START_REVIEW_SESSIONS`). The LLM's key sits in the same file and reaches the session's environment only. Origin: internal.
- **The tester and the coder in sessions of their own (stages 5 and 6).** One fresh session per component, one after another: the tester (`agent/write_unit_tests_prompt.md`) in a copy of the committed head without a code file, so it never reads the code, also on a rerun after a requirement change; only the component's test files, the stub of a unit with no code yet and the verification plan come back, anything else is refused and listed. The coder (`agent/write_unit_code_prompt.md`) works in the product. The red run is the gates', on the commit. `agent/count_retries_tool.py --component` counts each component's attempts. Origin: internal.
- **Clarify in a folder of its own files.** The clarify session runs through the launcher in a temporary folder of the requirements, the glossary and the diagrams; its questions land in `.qf/sessions/clarify.yaml`. Origin: internal.

### Changed

- **No LLM is the default.** The watcher reads `~/.aspice_agent_secrets/.env`; `--command`, the Claude Code commands and their allowed-tools lists are gone. The reviewer's read-only setting is the person's command. Origin: internal.
- **One folder for the agent's secrets.** The reviewer token moved to `~/.aspice_agent_secrets/reviewer_bot_github_token/<owner>`, still a file of its own that no framework tool reads. Origin: internal.
- **`.env` in the product's `.gitignore`.** `tools/create_product_tool.py` adds it with the agent's other lines. Origin: internal.
- **Archify in `.agents/skills`.** QUICKSTART step 7 installs it in the folder every agent host can use; `.claude/skills` is still searched. The session prompts' examples name no agent. Origin: internal.

## [4.0.4] - 2026-11-02

An answer names no one: the agent records the option the person chose, and the person's approval of the pull request that carries it says who answered.

### Migration

| Edit | Where | Required |
|---|---|---|
| None: answers and decision records written before keep their `approver` or `answered_by`, which nothing reads any more | — | — |

### Fixed

- **Answers were written in the person's name.** `agent/record_answer_tool.py --question Q<n> --choice N` no longer takes `--approver` and `--role`, and `agent/render_decisions_tool.py --ask ADR-NNNN --answer TEXT` no longer takes `--by`. The agent's permission check refused to write a decision in the person's name, and the name proved nothing. The person still answers in the terminal. The architect's approval of the `checkpoint/2` pull request, or the person's approval of the results review, covers the answers it carries. question.v1 no longer requires `answer.approver`. verify_decision_records_gate no longer requires `answered_by`. The pages show the answer without a name. Origin: FB-74 (wp_publisher).

## [4.0.3] - 2026-11-02

FB-72's fix also holds on the CI run a review starts: the checkpoint branch is read from the run's event.

### Migration

| Edit | Where | Required |
|---|---|---|
| None | — | — |

### Fixed

- **A review's CI run did not find the checkpoint branch.** `branch()` read `GITHUB_HEAD_REF`, which GitHub sets only on `pull_request` runs. A `pull_request_review` run has it empty and checks out a detached merge ref, so the approval of a `checkpoint/<n>` pull request turned its approval gate red again. `branch()` now reads the head branch from the event file (`pull_request.head.ref`, present on both events) first. `tools/read_commit_range_tool.py`. Origin: FB-73 (wp_publisher).

## [4.0.2] - 2026-11-02

A pull request from `checkpoint/<n>` that changes approved work can merge: its approval waits for that merge instead of failing CI.

### Migration

| Edit | Where | Required |
|---|---|---|
| None | — | — |

### Fixed

- **A changed checkpoint deadlocked.** Once checkpoint *n* had been approved, its stage counted as finished, so on a new `checkpoint/<n>` pull request the approval gate's own APPROVAL_OUTDATED (or MISSING_APPROVAL) failed CI. Only the merge makes the approval current, and the merge waited for a green CI. On branch `checkpoint/<n>` (`GITHUB_HEAD_REF` in CI, else the checked-out branch), the resolver now stops at the stage closing checkpoint *n*: those two findings are reported, every other finding of its work fails, and the architect's approval of the head is still required. `agent/resolve_stage_tool.py`. Origin: FB-72 (wp_publisher).

## [4.0.1] - 2026-11-02

A choice asked on an issue shows no boxes: the person answers with their own comment, and the card says so first.

### Migration

| Edit | Where | Required |
|---|---|---|
| None | — | — |

### Fixed

- **A tick on an issue's choice looked like an approval.** `agent/ask_person_tool.py --markdown` showed a box per option, but only the person's own comment (`/approve-change`, `/confirm-change`) answers on an issue: a tick edits the agent's comment and proves no person. The card now starts with *How to answer: comment on this issue exactly the command your option names. Ticking or editing this comment answers nothing.* and lists the options by number. `record_checkpoint_tool` names the clicks: *Files changed → Review changes → Approve, or Request changes with the reason*. `tools/render_page_tool.py`, `agent/record_checkpoint_tool.py`. Origin: FB-71 (wp_publisher).

## [4.0.0] - 2026-10-30

A checkpoint is its pull request: the architect approves it on GitHub, the agent merges it, and the merge is the record. No file, no copy, no paste; the customer needs no GitHub account.

### Migration

| Edit | Where | Required |
|---|---|---|
| Add `architect: <login>` under `review:`, and `customer: <name>` at the top level | `qf.yaml` | required: qf.v1 needs both |
| Copy `templates/github/release.yml` again (it publishes the GitHub Release) | `.github/workflows/release.yml` | required for the GitHub Release |
| For each checkpoint already approved by a file (1, 2, 3, in that order): branch `checkpoint/<n>` from main, delete that checkpoint's files (`<approvals_dir>/*-checkpoint-<n>-*.yaml`), push, open the pull request, run `record_checkpoint_tool.py --checkpoint <n> --pull-request <number>`; the architect approves it on GitHub | the product | required: until then the resolver finds no approval and sends the product back to checkpoint 1 |
| A release pull request still open on `release/v<version>`: close it and open it again from `checkpoint/5` | the product | required for that release |
| — | — | none for stage done records: they stay where they are and count as before |

### Changed

- **A checkpoint is its pull request, approved by the architect and merged.** v3.10.0 copied the person's review into an approval file and then needed CI to prove each copy — only for the copies a pull request changed, and the resolver trusted copies offline — while the customer at checkpoint 5 needed a GitHub account. Now the work of checkpoint *n* travels from branch `checkpoint/<n>`; qf.yaml `review.architect` approves its head on GitHub, or requests changes with the reason — at checkpoint 5 on behalf of qf.yaml `customer`. `record_checkpoint_tool --checkpoint N --pull-request N` waits for that decision (it checks every 30 seconds; the watcher opens the pull request for the person), merges the approved head with a merge commit once the crossing sign says *Ready to merge*, and prints the reason of a request for changes (exit 4). The merge commit is the record: the approval gates and the review pages read it from git history (`read_approvals_tool`), and a changed file withdraws it as before. `verify_delivery_reviewed_gate` holds a checkpoint pull request until the architect approves its head (MISSING_PERSON_APPROVAL), and checks the latest merge of every checkpoint against GitHub on every run (UNAPPROVED_MERGE). After the merge of `checkpoint/5`, the release workflow tags it and publishes the GitHub Release — *Release &lt;version&gt;. Accepted on behalf of &lt;customer&gt; by @&lt;architect&gt;, #&lt;number&gt;.* (`write_release_tool --notes`) — and the tool opens it. Works on GitHub's free plan for a private repository: no branch protection, no environment. Removed: `approval.v1` and its examples, the approval file of the example product, UNPROVEN_CHECKPOINT_DECISION, MISSING_CUSTOMER_DECISION, RELEASE_REJECTED, and APPROVED_TOO_LATE — the flow makes the order structural: derived work starts on the main branch after the checkpoint's merge. `create_product_tool` asks `--architect` and `--customer`. The branch form `release/v<version>` became `checkpoint/<n>` (BAD_BRANCH_NAME), and the track rule accepts `checkpoint/3`, the stack's checkpoint, as an architecture branch. `agent/record_checkpoint_tool.py`, `tools/read_approvals_tool.py`, `tools/check_approval_order_tool.py`, `tools/read_host_tool.py` (a pull request's branch, a release's page), `tools/write_release_tool.py`, `gates/sup/verify_delivery_reviewed_gate.py`, `gates/sup/check_commit_conventions_gate.py`, `gates/sup/check_track_rule_gate.py`, `gates/val/verify_release_evidence_gate.py`, `templates/github/release.yml`, `agent/run_aspice_agent.md` step 8, `agent/start_product.md`, QUICKSTART step 3, the rulebooks, design document § 5 *The checkpoints* and stages 10 and 11, Appendix A.8 *The checkpoint is its merged pull request*, A.9 *Branch names*, A.10 *Seal 5*. Origin: FB-69 (wp_publisher), Alex.

## [3.10.0] - 2026-10-30

Every checkpoint decision is given on the code host: the person approves or requests changes on the pull request, once, and pastes nothing.

### Migration

| Edit | Where | Required |
|---|---|---|
| Run `record_checkpoint_tool.py --checkpoint N --pull-request N` with `QF_HOST_TOKEN` set (e.g. `$(gh auth token)`) in place of `--decision/--approver/--role/--comment` | the agent's sessions | required: the old options are gone |
| The customer of checkpoint 5 needs a code host account to review the release pull request | the product's people | required for the next release |
| — | — | none for records already on the main branch: they stay as they are and count as before. A record a pull request adds or changes must name the person's review (UNPROVEN_CHECKPOINT_DECISION). |

### Changed

- **The person decides each checkpoint on the code host, once.** v3.9.0 kept the decision file and asked a person to approve the pull request that brought it, so the person decided twice — a pasted command in the session, an approval on the host. Now the person approves the pull request, or requests changes with the reason, and `record_checkpoint_tool --checkpoint N --pull-request N` copies that review — who, which review, which commit — as the approval file the resolver reads offline; with no person's decision yet it opens the pull request's changes in the browser and exits 3. A review by a review agent, a bot or the pull request's author decides nothing, and a review of files changed since is not copied. `approval.v1` gains `review` (pull_request, id, commit). `verify_delivery_reviewed_gate` checks every checkpoint record an open pull request adds or changes against the review it names (UNPROVEN_CHECKPOINT_DECISION); v3.9.0's rule calling a person for a decision file is gone. Seal 5 is the customer's review of the release pull request. `agent/record_checkpoint_tool.py`, `tools/read_host_tool.py` (a review's id), `validate_release_skill`, `verify_release_evidence_gate`, `agent/run_aspice_agent.md`, design document § 5 *The checkpoints*, Appendix A.8 *Who proves a recorded checkpoint decision*, A.10 *Seal 5*. Origin: FB-69 (wp_publisher), Alex.

## [3.9.1] - 2026-10-30

The page where the person approves a pull request opens for them.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none |

### Added

- **The review watcher opens where the person acts.** When a pull request waits for a person's review, `tools/watch_reviews_tool.py` opens the checkpoint-4 comment, else the pull request's changes, in the browser of the computer it runs on, once per head, and says so on its line; the person never copies a link. `open_page` (`tools/render_page_tool.py`) opens a link on the code host as well as a file. Design document § 5 *One layout for the person*, Appendix A.8 *Who proves a recorded checkpoint decision*. Origin: FB-68 (wp_publisher).

## [3.9.0] - 2026-10-30

A checkpoint decision recorded in the repository is proved the person's by their approval on the code host.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none. A pull request that adds or changes a checkpoint decision (`<approvals_dir>/*-checkpoint-<n>-*.yaml`) now needs a person's approval on the code host before it merges: MISSING_PERSON_APPROVAL until they approve. Records already on the main branch stay as they are. |

### Changed

- **A recorded checkpoint decision calls a person.** The decisions of checkpoints 1, 2, 3 and 5 are files anyone could write, and the gates counted each alike. A pull request that adds or changes one now calls a person (`classify_pull_request_tool`), so `verify_delivery_reviewed_gate` merges it only with their approval on the code host — the proof seal 4 already has. `agent/run_aspice_agent.md`, design document § 5 rule 14 of the quality assurance stage, Appendix A.8 *Who proves a recorded checkpoint decision*. Origin: FB-68 (wp_publisher).

## [3.8.3] - 2026-10-29

A requirement measured by the unit or the integration suite now has a stage that writes its measurement.

### Migration

| Edit | Where | Required |
|---|---|---|
| Add the measuring test of every requirement with *instrument: integration*, and *measurements* on the plan's *integration* suite, in a commit with no code | `<integration_tests_dir>`, verification plan | required on a product past stage 7: MISSING_MEASUREMENT at stage 8 until done |
| Change the instrument of a requirement with *instrument: unit* whose unit is already built, by a change request (e.g. to *integration*) | the requirement | required on a product past stage 5: its measuring unit test cannot be written before its code |

### Fixed

- **A unit or integration measurement had no stage that wrote it.** Only the software tests plugin said to write a measuring test, under the software tests folder, so a requirement whose instrument is *unit* or *integration* stayed MISSING_MEASUREMENT. The measuring test is now written at the instrument's stage: `derive_unit_tests_plugin` (stage 5, red on the stub) and `derive_integration_tests_plugin` (stage 7), each naming *measurements* on its suite; `derive_software_tests_plugin` writes the others. `verify_software_skill`, `specify_nfr_measurement_skill` R8, design document § 5 SWE.6, Appendix A.7 *Who writes a unit or integration measurement*. Origin: FB-67 (wp_publisher).

## [3.8.2] - 2026-10-29

A test renamed after its code was built no longer blames the test before it.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none |

### Fixed

- **A test renamed later made its neighbour judged at the commit that added it.** `verify_test_first_gate` cut each file at an older commit by the test names of the latest red run, so a test renamed since was no boundary there: its lines fell to the test above, which was judged at that commit and passed on the code it already had. In a Python file, the tests the file defines at the commit are boundaries too. `gates/swe/verify_test_first_gate.py`, design document § 5 SWE.4, Appendix A *A test renamed later*. Origin: FB-66 (wp_publisher).

## [3.8.1] - 2026-10-29

A changed requirement no longer needs a decision record of its own: the person gets a card only for a real choice.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none. A detailed design brought up to a change request is recorded again once its gates pass; a decision record written only to satisfy the v3.8.0 rule may be kept or removed. |

### Fixed

- **A changed requirement asked a card with nothing to choose.** `record_stage_done_tool` recorded the detailed design again only once each changed requirement was served by a decision record since the previous record — the person's for a critical one — so a critical requirement whose build holds no choice became a card that asks nothing. The rule is gone: a decision record is written only for a real choice, and `verify_decision_records_gate` (AGENT_DECIDED_CRITICAL) keeps a critical choice the person's. `agent/record_stage_done_tool.py`, `record_decisions_skill`, `derive_detailed_design_plugin`, `agent/run_aspice_agent.md`, design document § 5 *What CI fails on*, Appendix A.4 *A change request on a built product*. Origin: FB-64 (wp_publisher).

## [3.8.0] - 2026-10-29

A change request on a built product goes back through the design; the person is asked only what a critical requirement depends on, always as the same card, and every other decision is written down where they can read and change it.

### Migration

| Edit | Where | Required |
|---|---|---|
| Render the diagrams review page again (`agent/render_diagram_review_tool.py`) and commit it | `<diagrams_dir>/review.html`, only while checkpoint 1 waits for its approval | required: REVIEW_PAGE_OUTDATED until done; an approved page is held by its approval |
| Render the requirements review page again (`agent/render_review_tool.py`) and commit it | `<requirements_dir>/review.html`, only while checkpoint 2 waits for its approval | required: REVIEW_PAGE_OUTDATED until done; an approved page is held by its approval |
| — | — | none otherwise. A product whose requirements changed since its stage-4 record goes back to stage 4 (by design, FB-63). A pull request waiting for its checkpoint-4 review gets its comment rewritten, nothing folded; the person ticks and approves it again. |

### Added

- **Stages 4 to 7 follow a change of the requirements.** A stage done record never went outdated, so after a change request on a built product the resolver sent it to checkpoint 4 with none of the change built. Now the stages built from the requirements (`built_from_requirements` in `agent/stages.yaml`: detailed design, unit tests, code, integration tests) are done only while no requirement was added or changed since their latest record, compared with the requirements at the record's commit (`tools/read_requirements_tool.changed_since`); the first of them is the current stage again — its work still enforced — the reason naming the requirements and the components that meet them. `record_stage_done_tool` records it again, naming them (`stage_done.v1 requirements_changed`); the detailed design only once each is served by a decision record since the previous record — the person's, accepted, for a critical one. `agent/resolve_stage_tool.py`, `agent/record_stage_done_tool.py`, `tools/read_approvals_tool.py`, `manage_changes_skill`, `agent/run_aspice_agent.md`, design document § 5 *What CI fails on*, Appendix A.4 *A change request on a built product*. Origin: FB-63 (wp_publisher).
- **Only a critical requirement asks the person; every decision on one page.** `decision.v1` gains `decided_by` (person | agent), `requirements`, `question`, `why_you`, `proposed_because`, `answered_by`, `not_critical`, `where` and `change_request`. The person decides only a choice a critical requirement depends on (criticality high, or kind security); the agent decides and writes down every other. New `agent/render_decisions_tool.py` writes `<decisions_dir>/index.html` — *Waiting for you*, *Answered by you*, *Decided by the agent* (each with a *Change this* link opening a change request filled in), *Recorded with the architecture* — asks the person's decision as the card (`--ask`) and records the answer (`--answer`, `--by`). A superseded choice is shown as *Before*, never asked again. `verify_decision_records_gate` gains INCOMPLETE_DECISION, UNKNOWN_REQUIREMENT, AGENT_DECIDED_CRITICAL, MISSING_DECISIONS_PAGE and DECISIONS_PAGE_OUTDATED; `record_decisions_skill` is loaded at stage 4 too (R6–R10); the detailed design plugin asks the person only on a critical requirement. Design document § 5 *Inside the ASPICE Agent*, Appendix A.4 *Who decides a design choice*. Origin: FB-63 (wp_publisher), Alex.
- **One layout for the person.** New `tools/render_page_tool.py`: the page frame, the sections and the card — Question, Why you, Before, Options, Select, Proposed, Answer — in the browser, the terminal and on the code host alike; nothing folded. The diagrams and requirements review pages and the decisions page are built on it, the checkpoint-2 questions are cards, and `ask_person_tool` prints the card. `choice.v1` gains `why_you` and `before`. A framework test (`tests/consistency/test_one_layout.py`) fails on a page written any other way, or folded. Appendix A.1 *One layout for the person*. Origin: internal (Alex).

### Changed

- **Nothing folded on the checkpoint-4 comment.** The head, the stories' sources and the files were folded under *Details for the record*; they are now shown, last. `tools/post_checkpoint_review_tool.py`. Origin: internal (Alex).

## [3.7.0] - 2026-10-27

Every decision put to a person has one plain pattern; review pages open themselves in the browser; *What you accepted* tells each answer as a short story.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.7.0. A pull request waiting for its checkpoint-4 review gets its comment rewritten in the new pattern; the person ticks and approves it again. |

### Added

- **One pattern for every decision.** The framework asked a person to decide in six different ways. Now each decision is a `choice.v1`, in plain language — *Question*, *Options* (explained in sentences, no requirement ID), *Select your option* (numbered labels) and, when something decides one, *Proposed* with its reason — printed by the new `agent/ask_person_tool.py` in the terminal or as Markdown with a box per option; the answer is only a listed number, or Y where a proposal is offered (`--answer` checks it). The checkpoint-4 comment's items, the watcher's *REVIEW STOPPED* banner (1 or R retries) and `record_answer_tool --ask` print through it; the agent, the plugins' rounds (the assumption becomes the proposal), the checkpoints, the escalation, the product start and the approvals asked on an issue follow it. `contracts/choice_contract.v1.schema.json`, `agent/run_aspice_agent.md`, `agent/start_product.md`, the requirements, architecture and validation plugins, `manage_changes_skill`, `resolve_problems_skill`, `track_nonconformances_skill`, `validate_release_skill`, design document § 5 *Inside the ASPICE Agent*, Appendix A.1 *One pattern for every decision*. Origin: internal (Alex).
- **Pages open themselves.** `render_review_tool` and `render_diagram_review_tool`, run from the command line, open the page they write in the browser and print its path — never in CI or a test run, nor with `--no-open`. Origin: internal (Alex).

### Changed

- ***What you accepted* in the person's words.** The summary named each answer by requirement ID and criterion number, with glossary terms unexplained. `question.v1` gains `situation` and, per reading, `label` and `means`, written by the criteria check without IDs or unexplained terms; the summary tells each answer as the question, *When* the situation, what the product will do, *For you* what it means, the risk, and the requirement's statement and ID last. `agent/record_answer_tool.py`, `agent/clarify_criteria_prompt.md`, `write_requirements_skill` R18, design document rule 27, Appendix A.2. Origin: FB-61 (wp_publisher).

## [3.6.0] - 2026-10-26

The criteria check before checkpoint 2 asks only what someone would notice, asks one rule once, and checks a rewrite again only once.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.6.0 |

### Changed

- **Rounds of questions end.** Each rewrite of a criterion raised a new round of questions one edge case deeper, some without a proposal although a convention settled them, and the same convention once per criterion. The check now asks only what the author or a system next to the product would notice; it proposes a convention also when unsure (the *What you accepted* summary marks it, and it can be answered again) and *no proposal* only when the readings are equally likely; one rule that settles several criteria or terms is one question, naming the others under the new optional `also` of `question.v1`, and its answer rewrites each. A criterion is checked again once after its rewrite: one settled at two texts since the latest approval of checkpoint 2 counts as checked when rewritten again. `agent/clarify_criteria_prompt.md`, `agent/record_answer_tool.py`, `contracts/question_contract.v1.schema.json`, `agent/run_aspice_agent.md` step 8, `derive_requirements_plugin` step 7, `write_requirements_skill` R18, design document § 5 rule 27, Appendix A.2 *Unclear criteria settled at checkpoint 2*. Origin: FB-60 (wp_publisher).

## [3.5.0] - 2026-10-26

Checkpoint 2 tells the person, in plain words, what their answers accept — the risky ones first — before anything is rewritten.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.5.0 |

### Added

- **What you accepted.** Accepting every proposal with one Y (v3.4.0) could let a risky reading through unseen. Before the criteria are rewritten, `record_answer_tool --summary` prints what each answer makes the product do, in plain words, the risky ones first, each marked ⚠ with why: a requirement of high criticality or about security, a glossary term every requirement using it follows, a reading that contradicts another requirement, a proposal from common practice rather than anything approved. The person keeps the answers with Y or answers any one again (`--again`, while its criterion is not rewritten). The criteria check writes each reading as a plain sentence of what the product does. `agent/record_answer_tool.py`, `agent/run_aspice_agent.md` step 8, `agent/clarify_criteria_prompt.md`, `write_requirements_skill` R18, design document § 5 rule 27, Appendix A.2 *Unclear criteria settled at checkpoint 2*. Origin: internal (Alex).

## [3.4.0] - 2026-10-26

Checkpoint 1 gets a review page with the rules and wish links; checkpoint 2 asks fewer, better-ordered questions; both pages open in the browser.

### Migration

| Edit | Where | Required |
|---|---|---|
| Render the diagrams review page — `python .framework/agent/render_diagram_review_tool.py --root .` — and commit it | `<diagrams_dir>/review.html` | required: MISSING_REVIEW_PAGE until it exists |
| Have the person approve checkpoint 1 again, on that page | `<approvals_dir>` | required: the approval now covers the page, so the earlier one is outdated (APPROVAL_OUTDATED) |

### Added

- **A review page for checkpoint 1.** A change to a diagram's rules or wish links was approved on a picture that shows neither. `agent/render_diagram_review_tool.py` renders `<diagrams_dir>/review.html`: per diagram its pictures, linked and shown in place, its rules and the wishes each element realises with their statements, what changed since the previous approval of checkpoint 1 marked. *check_diagram_contract_gate* reports MISSING_REVIEW_PAGE and, until checkpoint 1 approves it, REVIEW_PAGE_OUTDATED; the approval covers the page, and record_checkpoint_tool refuses one on a stale page. `draw_diagram_skill` R15, R16, design document § 5 stages 1 and 2 rules 22–25, Appendix A.2 *What the person approves*. Origin: FB-57 (wp_publisher).

### Changed

- **The pages open in the browser.** At checkpoints 1 and 2 the agent opens the review page in the browser of the person's computer, once per decision, and prints its full path; checkpoint 3 prints the stack table and the full path of its decision record. `agent/run_aspice_agent.md` step 8. Origin: FB-56 (wp_publisher).
- **Questions numbered as the page shows them.** `record_answer_tool --questions` numbers the questions in the review page's order, top to bottom, and the agent asks them in that order. Origin: FB-58 (wp_publisher).
- **Fewer questions at checkpoint 2.** A change request checked every criterion again — 27 questions, most with a conventional answer. Now a criterion unchanged since the latest approval of checkpoint 2 counts as checked; a criterion rewritten to settle a question is listed with it, and the check asks only about the wording the rewrite added; a proposal may name *convention: …*, the behaviour every tool of the kind has without being told. The questions with a proposal are accepted in one list with Y, any one opened by number; those without are asked one at a time. The build is not a source: the check questions what was built. `agent/record_answer_tool.py`, `agent/clarify_criteria_prompt.md`, `agent/run_aspice_agent.md` step 8, `derive_requirements_plugin` step 7, `write_requirements_skill` R18, design document § 5 rule 27, Appendix A.2 *Unclear criteria settled at checkpoint 2*. Origin: FB-59 (wp_publisher).

## [3.3.1] - 2026-10-26

qf/merge tells a head the reviewer agent sent back from one not reviewed yet.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.3.1 |

### Fixed

- **A change request read as "not reviewed yet".** After the reviewer agent requested changes on the head, qf/merge still said *Wait: the reviewer agent's approval*, the text of a head not yet reviewed, so the author agent waited instead of fixing. *verify_delivery_reviewed_gate*'s MISSING_AGENT_REVIEW now says when a reviewer agent's latest decision requests changes on the head, and qf/merge says *Wait: changes requested by the reviewer agent: fix the findings and push*. `agent/run_aspice_agent.md` says where the findings are: the review's body and its line comments. `tools/post_merge_status_tool.py`, `gates/sup/verify_delivery_reviewed_gate.py`, `QUICKSTART.md`, design document § 5 stage 9 rule 13. Origin: FB-55 (wp_publisher).

## [3.3.0] - 2026-10-26

A design's open question says what keeping it keeps.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.3.0; an open pull request whose design has a gap meets INCOMPLETE_CHECKLIST until its next head is reviewed |

### Added

- **What the build does at each gap of a design.** The checkpoint-4 comment asked the person to keep a gap of a design — "the design does not say whether the workbook is written once or after each row" — without saying what the build does there, so *keep* kept something unnamed. The review record (review.v1) gains `gaps`: for each gap the reviewer agent approves, what the build does there now, the lines that decide it (`path:line`) and what follows for the user; with no line deciding it yet, the reading the build will take. The comment shows it as **Now:** and **For the user:** before the choice, now *keep it as it is now* or *change it*. *verify_delivery_reviewed_gate* reports INCOMPLETE_CHECKLIST for an approved gap with none, or a named line the product does not have. `contracts/review_contract.v1.schema.json`, `tools/post_checkpoint_review_tool.py`, `gates/sup/verify_delivery_reviewed_gate.py`, `tools/watch_reviews_tool.py`, `agent/run_reviewer_agent.md`, `skills/sup/review_code_skill/SKILL.md` R16, `plugins/sup/derive_review_plugin/SKILL.md`, design document § 5 stage 9, Appendix A.8 *What a kept gap keeps*. Origin: FB-54 (wp_publisher).

## [3.2.1] - 2026-10-26

A pull request behind main catches up by a merge, never a rebase.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.2.1 |

### Fixed

- **A rebase was offered as an equal way to bring a refused push up to date.** On a pushed pull request branch a rebase rewrites its history: the next push goes through only as a force-push, and the stage done records and reviews name commits the branch no longer holds. The rulebooks now forbid rewriting any pushed branch: a pull request behind main catches up by merging main into its branch, and a rebase is left to a branch never pushed. `skills/sup/record_baseline_skill/SKILL.md` R13, `agent/run_aspice_agent.md`, `QUICKSTART.md`, design document § 5 stage 10 rule 7. Origin: FB-53 (wp_publisher).

## [3.2.0] - 2026-10-26

Unclear criteria are settled by the person before the build, and the reviewer agent compares the tests with cases listed from the criteria alone.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.2.0 |

Requirements already approved at checkpoint 2 are not checked again until they change. Requirements not yet approved meet CRITERIA_NOT_CHECKED until the agent runs the check. An open pull request that brings the results meets REVIEW_EXPECTED_CASES_MISSING until its next head is reviewed.

### Added

- **Unclear criteria settled at checkpoint 2.** The tester, the coder and the reviewer agent run the same model on the same text, so a criterion read two ways was read the same wrong way by all three. Before checkpoint 2 a fresh session that sees only the requirements, the glossary and the approved diagrams (`agent/clarify_criteria_prompt.md`) flags each criterion or glossary term whose readings would need different tests, each reading with an example, a reading that contradicts another requirement marked, and a proposal only with its source. `agent/record_answer_tool.py` records the questions in `<requirements_dir>/questions.yaml` (new contract `question.v1`) with the SHA-256 of every criterion and term checked, so an unchanged one is not asked again, and records each answer. The questions sit in their requirement's row of the review page; the agent asks them one at a time in the terminal, the person answers with a listed number or Y for the proposal, and the agent rewrites the criterion and has it checked again. *verify_requirements_approval_gate* gains CRITERIA_NOT_CHECKED and QUESTION_UNANSWERED; *record_checkpoint_tool* refuses an approval while a question is open; the approval covers `questions.yaml`. `derive_requirements_plugin` step 7, `agent/run_aspice_agent.md` § 8, `write_requirements_skill` R18, design document § 5 stages 1 and 2 rule 27, Appendix A.2. Origin: internal (the reviewer's independence, Appendix A.8).
- **Expected cases with the results.** Before reviewing a pull request that brings the results, the watcher runs a session that sees only the statement and criteria of the requirements proved and the glossary (`agent/expect_cases_prompt.md`) and lists the cases each criterion needs tested, kept in `.qf/reviews/<n>-<sha>.expected.yaml`. The reviewer agent copies them into its record's new `expected` field (`review.v1`) with the test that checks each, or `missing`: a missing case is a finding for the tester, a case held wrong a question for a person. *verify_delivery_reviewed_gate* gains REVIEW_EXPECTED_CASES_MISSING. `tools/watch_reviews_tool.py`, `agent/run_reviewer_agent.md`, `review_code_skill` R17, design document § 5 stage 9 rule 14, Appendix A.8. Origin: internal (the reviewer's independence, Appendix A.8).

## [3.1.3] - 2026-10-26

A renamed test, a new assumption or a changed test double no longer fails the red run of a built unit.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.1.3 |

### Fixed

- **v3.1.2's per-test judging still blocked review fixes.** A test's lines were compared with the parent's file cut by the new commit's test names, so a renamed or removed test made the test before it changed; and any change before the first test judged every test of the file, so a new assumption in the module docstring or a test double following a changed interface met TEST_NOT_FAILING for every test on the built unit. *verify_test_first_gate* now reads the commit's diff: a test changed when code among its own lines changed — its annotations and the comments right above it included — while blank lines, comments and docstrings change nothing and a test removed between two others changes neither. Code changed before the first test (imports, fixtures, helpers) judges no test by itself, but one of the file's tests must fail on that commit, else TEST_NOT_FAILING names the file. `gates/swe/verify_test_first_gate.py`, `skills/swe/enforce_test_first_skill/SKILL.md` R4, design document § 5 unit stages rule 18, Appendix A.5. Origin: FB-52 (wp_publisher).

## [3.1.2] - 2026-10-25

A built unit's tests change test-first again.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.1.2 |

### Fixed

- **The red run judged a test file, not a test.** Once a unit's code existed, a test-only commit that added or changed one test of its file met TEST_NOT_FAILING for every unchanged test of that file, so no review finding or change request on a built unit could be fixed test-first. *verify_test_first_gate* now judges each test at the last test-only commit that changed it: a test is found in its file by its name (parameters left out), and it changed when its lines — up to the next test, trailing comments, blank lines and annotations left out — differ from the commit's parent. A change before the first test (imports, fixtures, helpers) judges every test of the file; a test whose name is not in its file is judged at the file's last test-only commit, as before. A test left as it was is no longer judged at a later commit that changes its file, but at its own. `gates/swe/verify_test_first_gate.py`, `skills/swe/enforce_test_first_skill/SKILL.md` R4, design document § 5 unit stages rule 18, Appendix A.5. Origin: FB-51 (wp_publisher).

## [3.1.1] - 2026-10-25

The composition root and a package's `__init__.py` pass stage 6.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.1.1 |

### Fixed

- **Two code files that implement no unit could not pass stage 6.** Every code file needed a unit marker, so the composition root, where the architecture puts it, met either MISSING_UNIT_MARKER or, with a marker, UNIT_OUTSIDE_COMPONENT; a package's `__init__.py` met MISSING_UNIT_MARKER. *verify_code_to_design_link_gate* now asks no marker of the file a component's `composition_root` names (its path ends with the root's module, e.g. `pkg/__main__.py` for `pkg.__main__.main`) nor of a file that holds no code (empty, or Python with a docstring alone); a marker in either is still checked as before. The coder's method places the composition root where the architecture names it and keeps logic out of it. `gates/swe/verify_code_to_design_link_gate.py`, `skills/swe/construct_units_skill/SKILL.md` R1, `plugins/swe/derive_unit_code_plugin/SKILL.md` *Steps*, design document § 5 unit stages rule 14, Appendix A.5. Origin: FB-50 (wp_publisher).

## [3.1.0] - 2026-10-25

The person is asked nothing during the build, a usage limit no longer stops a review for good, and a tick changed after the approval says what to do.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.1.0 |

### Changed

- **No person is asked during the build.** The *Ask* section of every plugin of stages 4 to 8 asked the person a round of build questions, against v3.0.0's split. The agent now settles them itself, writes each choice as a stated assumption in the work (the design as a decision `D<n> — assumed: …`, a test's docstring and the verification plan, a comment in the code and the commit message), and goes on; the reviewer agent judges every assumption. A question of what is wanted — no requirement answers it, and it changes what the user sees or gets — reaches the person only through the reviewer agent: a design's gap (⚠), or a change request. `plugins/swe/derive_{detailed_design,unit_tests,unit_code,integration_tests,software_tests}_plugin/SKILL.md`, `agent/run_aspice_agent.md` § 6, design document § 3 (method sections), Appendix A.8. Origin: FB-49 (wp_publisher).

### Fixed

- **The reviewer's record rule was ignored.** Claude Code matches file permissions by `Edit` rules only, so `Write(.qf/reviews/**)` allowed nothing; the watcher now allows `Edit(.qf/reviews/**)`. `tools/watch_reviews_tool.py`. Origin: FB-47 (wp_publisher).
- **A review stopped by the agent's usage limit was never tried again.** The watcher recognises the limit and tries that head again every 10 minutes, one line each time, until a review is posted; a closed pull request or a newer head ends the tries. `tools/watch_reviews_tool.py`, design document (the watcher), `QUICKSTART.md`. Origin: FB-47 (wp_publisher).
- **A tick changed after the approval waited without a word.** Only an approval reads the ticks, and an edit of the comment runs no gates; the comment's *How to answer* and the crossing sign for unanswered items now say *approve again*. A run on the comment's edits was not taken (Appendix A.8). `tools/post_checkpoint_review_tool.py`, `tools/post_merge_status_tool.py`, design document (stage 9), `QUICKSTART.md`. Origin: FB-48 (wp_publisher).

## [3.0.1] - 2026-10-25

The author goes on working while the watcher reviews.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v3.0.1 |

### Fixed

- **The watcher blamed the reviewer for the author's and the framework's own edits, and paused every review.** It compared the whole product folder before and after each session, while the author and the framework's answers to feedback wrote into it. The session now runs in a copy of the pull request's head of its own, a git worktree the watcher makes at `.qf/reviews/<n>-<sha>/`, and only that copy is compared: a change there is the reviewer's, shown as *REVIEWER CHANGED THE WORK* with the copy kept to see it. After a review the session's records go to the product's `.qf/reviews/` and the copy is removed; a head that cannot be fetched stops its review. The framework is reached by its full path, since the copy has no `.framework`. `tools/watch_reviews_tool.py`, `agent/run_reviewer_agent.md` § 3, design document (the watcher), `QUICKSTART.md`. Origin: FB-46 (wp_publisher).

## [3.0.0] - 2026-10-25

The person decides what is wanted and whether it was achieved; the build in between is the agents' and the gates'. Checkpoint 4 becomes the approval of the results.

### Migration

| Edit | Where | Required |
|---|---|---|
| Copy the step *Checkpoint-4 review: post it when a person must review* to right after *Write the verification report*, and keep every step that runs a framework command as the template has it | `.github/workflows/quality_gates.yml` (from `templates/github/quality_gates.yml`) | required: CI_FILE_NOT_TEMPLATE fails until the CI file keeps the template's steps, order, triggers and permissions |
| Move the pin to v3.0.0; a pull request reviewed at an earlier version needs the reviewer agent's review again | the framework submodule | required |

### Changed

- **No person's review of the build.** A changed detailed design, unit and integration tests, code and build files merge on the reviewer agent and the gates, whatever the requirements' ratings; the importance triggers (high or security requirement, trust boundary, untraced file) no longer call a person. `tools/classify_pull_request_tool.py`. Origin: FB-45 (wp_publisher).
- **Checkpoint 4 is the approval of the results**, closing stage 8 (`agent/stages.yaml`): on the pull request that adds or changes software-level tests, CI posts the results from the verification report — one line per requirement of criticality high or of kind security it proves and per requirement that did not pass, with its tests described from the test alone, the measured value next to its threshold and the result — answered *achieved* or *not achieved*; the rest only counted. The review comment is posted after the verification report; without one, the gate waits (REVIEW_ITEMS_UNANSWERED). `tools/post_checkpoint_review_tool.py`, `templates/github/quality_gates.yml`. Origin: FB-45 (wp_publisher).
- **During the build the person is asked only a question of what is wanted:** a gap (⚠) of a design's story that the reviewer agent approved — no requirement answers it — answered *keep the requirements* or *change them*; a weakened test; a finding closed without a change; the reviewer agent's request. Every changed design is told as stories whether or not a person is called; the reviewer agent turns a gap a requirement answers into a finding. *covers* left *review.v1*. `agent/run_reviewer_agent.md`, `plugins/sup/derive_review_plugin/SKILL.md`, `skills/sup/review_code_skill/SKILL.md` (R4, R12, R16). Origin: FB-45 (wp_publisher).
- **The gates' own files:** a framework pin moved to a released tag and a CI file kept to the template need no person; *qf.yaml* and *.gitmodules* still do. Origin: FB-45 (wp_publisher).
- **"Checked by: Checkpoint 4" became "Checked by: Review"** in the rulebooks: the reviewer agent's judgement at the pull request. Origin: FB-45 (wp_publisher).
- **The example product's CI file** matches the template again; it lacked the crossing sign and the review comment. Origin: internal.

### Added

- **CI_FILE_NOT_TEMPLATE** (*verify_required_checks_gate*): the product's CI file departs from the framework's template in a step that runs a framework command (missing, changed, out of order, allowed to fail silently), or in its triggers or permissions. Origin: FB-45 (wp_publisher).

## [2.6.0] - 2026-10-25

The person's review reads without code: what the pull request does, why the person is asked, and each design told as a story next to the requirement it must satisfy.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v2.6.0; a pull request a person reviews needs the reviewer agent's review again at this version, since its record now carries the summary, the stories and *covers* |

### Changed

- **The checkpoint-4 comment is readable without code.** It opens with what the pull request does (the record's new *summary*), why the person is asked in one plain sentence with counts — "It touches 12 high-criticality requirements and 1 security requirement" — instead of lists of IDs and arrows, and how to answer; IDs, the head and the files are folded at the end under *Details for the record*. A test is told as *Given · When · Then it checks · It does not check*. `tools/post_checkpoint_review_tool.py`, `tools/classify_pull_request_tool.py` (*brief*, *asked*, *headline*). Origin: FB-44 (wp_publisher).
- **A changed detailed design is asked as stories, not "does it fit REQ-0101 … REQ-0145?".** A session that sees the design files only, never the requirements, tells it as situations step by step in plain words, with the design's values; at every step that waits or receives it asks what if no answer comes, the answer is wrong, a limit is exceeded, and where the design does not say, it writes so as a step marked ⚠ instead of a guess. Each step names its sources — `message:<id>`, `unit:<id>`, `decision:<label>`. The reviewer agent, which saw both, names the story that shows each requirement of criticality high or of kind security the design serves (*covers*). The person gets one question per such story, the requirements' text above its steps, and one per such requirement no story shows. The watcher runs the session like the test describer, in a temporary folder of the design files only, and checks every source. New `agent/describe_design_prompt.md`; *review.v1* gains *summary*, *stories* and *covers*; `tools/watch_reviews_tool.py`, `agent/run_reviewer_agent.md`, `plugins/sup/derive_review_plugin/SKILL.md`. Origin: FB-44 (wp_publisher).
- **The crossing sign and the watcher name the person, the reason and the address.** *qf/merge* reads, for example, `Wait: a review by alexxo (it changes the quality gates' own files): approve on GitHub`, and the watcher `waits for a review by alexxo: <the comment's address>`, else the pull request's changes. `tools/post_merge_status_tool.py`, `tools/watch_reviews_tool.py`. Origin: FB-43 (wp_publisher).
- **A person with nothing to tick still gets the comment**, saying who is asked, why, and that the approval alone is the review; before, CI posted nothing and the status was the only trace. Origin: FB-43 (wp_publisher).
- **The describe sessions run without the reviewer's token.** They read copied files only; the token was inherited but unused. `tools/watch_reviews_tool.py`. Origin: internal.

### Added

- **REVIEW_STORY_UNSOURCED** (*verify_delivery_reviewed_gate*): a story step whose source its design does not have; *INCOMPLETE_CHECKLIST* also covers a record without the summary, a changed design without stories, or an asked requirement without its story. `skills/sup/review_code_skill/SKILL.md` R12 and R15. Origin: FB-44 (wp_publisher).

## [2.5.7] - 2026-10-24

The watcher starts again.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: move the pin to v2.5.7 |

### Fixed

- **The watcher crashed at start** with `TypeError: 'bool' object is not callable`. v2.5.6 added the field *describe* to *Watcher* before *out*, while `main()` built it by position: `print` landed in *describe* and the colour flag in *out*. `main()` now builds it by keyword, and a test runs `main()` to its first look on a recorded host, so a field order change breaks a test instead of the start. The watcher's other tests built *Watcher* by keyword and never ran `main()`. `tools/watch_reviews_tool.py`. Origin: FB-42 (wp_publisher).

## [2.5.6] - 2026-10-24

The tests are described blind by construction: the watcher writes the descriptions itself.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none |

### Changed

- **The watcher runs the describe session, in a folder of tests only.** Before each review, `tools/watch_reviews_tool.py` fetches the pull request's head, asks *classify_pull_request_tool* which tests a person would review (its new *candidates*), copies those files alone into an empty temporary folder outside the product, and runs the describe session there with the reading tool only and the instructions in its prompt — the session has no path to the requirements, whatever the agent. The answer is checked against *review.v1* and every test file must be described; otherwise the review does not start and the *REVIEW STOPPED* banner says why. The reviewer agent copies the list into its record unchanged and never describes a test itself. Before, the separation rested on the reviewer agent's instructions alone. `agent/run_reviewer_agent.md`, `agent/describe_tests_prompt.md`, `review_code_skill`; design document § 5 stage 9, rule 14. Origin: internal (review of the watcher with Alex).

## [2.5.5] - 2026-10-24

The reviewer's token is given to the watcher alone.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: start the watcher with the one-line command of QUICKSTART step 9 instead of exporting the token first |

### Changed

- **The token lives in the watcher only.** QUICKSTART step 9 starts the watcher in one line that hands it the reviewer agent's token — macOS (zsh or bash) and Linux `QF_HOST_TOKEN="$(cat …)" python …`, PowerShell `try { … } finally { Remove-Item Env:QF_HOST_TOKEN }` — instead of exporting it into the terminal for the day: later commands in that terminal never inherit it, the shell's history keeps the command and not the token, and it is gone when the watcher stops. No framework tool reads the token file, as before. `tools/watch_reviews_tool.py` (its usage and missing-token message); design document § 5 stage 9, rule 1. Origin: internal (review of the watcher with Alex).

## [2.5.4] - 2026-10-24

A reviewer never changes the work: the watcher checks it, whatever the agent.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none; with another agent than Claude Code (`--command`), configure it read-only |

### Added

- **The watcher catches a reviewer that changed the work.** The agent's settings prevent it — Claude Code's allowed tools by default — and `tools/watch_reviews_tool.py` now checks it with any agent: it compares the product folder's commit and changed files (`.qf/` left out) before and after each session. On a change it shows the banner *REVIEWER CHANGED THE WORK* — what changed, "verify your LLM settings", check the change with the author — with a desktop notification, and pauses every review until the person types `R`. Design document § 5 stage 9, rule 1; QUICKSTART. Origin: internal (review of the watcher with Alex).

## [2.5.3] - 2026-10-24

The watcher says what each pull request waits for.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none |

### Changed

- **One line per change of a pull request's state.** `tools/watch_reviews_tool.py` no longer stays silent while CI runs or is red: it writes *waits for CI (gates running)*, *gates red (<gates>): the author fixes them, no review yet*, *waits for your review: the link is in the pull request* or *ready to merge; the agent merges*, each once per change, and warns *no crossing sign after 10 min: check that CI runs*. Design document § 5 stage 9, rule 1; QUICKSTART. Origin: internal (review of the watcher with Alex).

## [2.5.2] - 2026-10-24

The watcher shows that a long review is alive, and stops a stuck one sooner.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none |

### Changed

- **A review session says it is still running, and may take 20 minutes.** `tools/watch_reviews_tool.py` prints `#<n> head <sha>: still reviewing (<m> min)` every 5 minutes, so the person sees a long review is alive, and stops a session after 20 minutes instead of 45 — a limit for a stuck one, shown as the *REVIEW STOPPED* banner. Reviews stay one at a time: a product rarely has two pull requests waiting. Design document § 5 stage 9, rule 1; Appendix A.8 "Who starts the reviewer agent"; QUICKSTART. Origin: internal (review of the watcher with Alex).

## [2.5.1] - 2026-10-24

The watcher points to the right QUICKSTART step.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none |

### Fixed

- **The watcher's missing-token message names QUICKSTART step 9**, where the watcher is described, not step 8. `tools/watch_reviews_tool.py`. Origin: internal.

## [2.5.0] - 2026-10-24

The reviewer agent starts on its own: a watcher the person starts once a day.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: start `python .framework/tools/watch_reviews_tool.py --root .` once a working day, in a terminal with the reviewer agent's token, instead of starting each review by hand |

### Added

- **The watcher, `tools/watch_reviews_tool.py`.** Started once a working day in a terminal of the person's own, with the reviewer agent's token, it starts a fresh reviewer session for every head of the product's open pull requests whose crossing sign waits for the reviewer agent and that it has not reviewed: one at a time, each head once, with the reviewer's tools only — reading, the host, the framework's own commands, its record's folder. Every event is one line; a session that ends without a review is a banner — *REVIEW STOPPED*, why, what to do, and its log under `.qf/reviews/` — red where the terminal shows colour, with a desktop notification on Windows, macOS and Linux; `R` reviews the stopped heads again, and Ctrl+C ends with the day's summary. `--command` replaces the agent command. Design document § 5 stage 9, rule 1; Appendix A.8 "Who starts the reviewer agent"; QUICKSTART; `agent/run_aspice_agent.md`, `agent/run_reviewer_agent.md`. Origin: FB-41 (wp_publisher), point 3.

## [2.4.0] - 2026-10-24

A person reviews what is important or risky, never a pull request chosen by number, on a review in plain words they answer item by item; a feature arrives in four pull requests.

### Migration

| Edit | Where | Required |
|---|---|---|
| Replace `sample_every: <N>` with `people: [<login>]`, the accounts CI mentions when a pull request needs a person's review | the product's `qf.yaml`, under `review` | required: `qf.v1` asks for `people` and no longer knows `sample_every` |
| Set `pull-requests: write` (was `read`) under `permissions`, and add the step *Checkpoint-4 review: post it when a person must review* before *Write the verification report*, as in `templates/github/quality_gates.yml` | the product's CI file (a code owner's change) | required: without the comment, a pull request a person must review waits (REVIEW_ITEMS_UNANSWERED) |

### Changed

- **A person reviews what is important or risky.** *verify_delivery_reviewed_gate* no longer samples 1 in N by pull-request number — blind to risk, and moved by every issue opened, since GitHub numbers issues and pull requests together. *classify_pull_request_tool* decides from the files: a requirement rated criticality high or of kind security at checkpoint 2, reached through the links the files carry (*@sdoc*, else *@unit* → component → *meets*; a detailed design takes its component's); a trust boundary; a file that traces to nothing (it counts as touching every requirement); a test deleted, fewer or switched off, or the plan's coverage minimum or time budget loosened; a finding withdrawn or disputed; the reviewer agent's request, for one of five conditions — it may add a review, never cancel one. No random floor. Architecture pull requests and the gates' own files are reviewed as before. Design document § 5 stage 9, rule 14; Appendix A.8 "The person's review by risk, in plain words". Origin: FB-41 (wp_publisher), points 1 and 5.
- **The person's review is in plain words, answered item by item.** Once the reviewer agent has approved, CI posts the checkpoint-4 review as a comment mentioning `review.people` (*post_checkpoint_review_tool*): why they are asked, then each changed detailed design, each test with the approved criteria next to the reviewer agent's description of it written from the test alone (*agent/describe_tests_prompt.md*), each weakened test, each dispute and the reviewer agent's request, each with a pair of boxes. The person ticks one per item, then approves or requests changes with the reason; the gate requires every item answered yes (REVIEW_ITEMS_UNANSWERED) and the comment unchanged since the approval (REVIEW_CHANGED_AFTER_APPROVAL). The author agent opens the comment on its computer. Design document § 5 stage 9, rules 13 and 14. Origin: FB-41 (wp_publisher), points 1 and 2.
- **The reviewer agent's approval carries its review record.** *post_review_tool --record* writes a *```yaml review* block (*review.v1*): whether it asks for a person, every finding's outcome, and the tests described for the person; an approval without it, or without a reviewed test's description, is INCOMPLETE_CHECKLIST. `agent/run_reviewer_agent.md`, `derive_review_plugin`, `review_code_skill` R12–R14. Origin: FB-41 (wp_publisher).
- **A feature arrives in four pull requests:** the detailed design; the unit tests with their code; the integration tests; the software tests. Design document § 5 stage 9, rule 15; Appendix A.8 "How big a feature pull request is"; `agent/run_aspice_agent.md`. Origin: FB-41 (wp_publisher), point 4.
- `create_product_tool` asks for `--person`; `agent/start_product.md` and the QUICKSTART name it.

## [2.3.2] - 2026-10-24

The author agent merges a pull request on *Ready to merge*; the person merges nothing.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: the agent's instructions change with the framework; the person stops merging |

### Fixed

- **Who merges is stated once.** The flow diagrams had the agent merge, while `agent/run_aspice_agent.md` and the QUICKSTART told "the person who merges" to wait for *qf/merge*: products read it as the person, who then waited on every pull request for a click that holds no judgement. The author agent now merges, only on *Ready to merge* and exactly the head that status belongs to (`gh pr merge --match-head-commit`), then waits for the main branch's run and reports a red one. The person's judgement stays their approval of a sampled pull request. Design document § 3 step 9, § 5 stage 9 rule 13, Appendix A.8 "Who merges"; QUICKSTART; `tools/post_merge_status_tool.py`; `templates/github/quality_gates.yml` (a comment). Origin: FB-41 (wp_publisher), point 3.

## [2.3.1] - 2026-10-24

A framework bump is accounted for in the product team's own words only.

### Migration

| Edit | Where | Required |
|---|---|---|
| — | — | none: a bump recorded in an entry's **Framework version** or a *No findings for* line, as the template asks, passes as before |

### Fixed

- **The framework's own answers no longer account for a bump.** *check_framework_feedback_gate* accepted a submodule bump when the new version appeared anywhere under **Log**, and every framework response quoted there names the version that resolves it: a team moving to exactly that version passed while recording nothing. The gate now reads only an entry's **Framework version** field and lines starting *No findings for*, and matches the version as a whole word, so `v2.2.1` no longer matches inside `v2.2.10` nor a short commit inside longer text. A version named in a Status or in prose ("fixed upstream in v2.2.2") no longer counts either. `report_framework_feedback_skill` R2; `templates/FRAMEWORK_FEEDBACK.md`; design document § 5 stage 9, rule 9. Origin: internal.

## [2.3.0] - 2026-10-23

Stage 1 requires an architecture diagram: the parts that become the components are approved with the diagrams.

### Migration

| Edit | Where | Required |
|---|---|---|
| Draw an architecture diagram whose nodes are the parts the sequence diagrams name, render and commit its picture, then approve the diagrams again at checkpoint 1 and the requirements at checkpoint 2 (§ 5 stages 1 and 2, rule 25) | the product's diagrams, only where *check_diagram_contract_gate* reports NO_ARCHITECTURE_DIAGRAM | required: stage 1 is a finished stage, so its finding fails CI |

### Changed

- **An architecture diagram is required at stage 1.** *check_diagram_contract_gate* reports NO_ARCHITECTURE_DIAGRAM, which replaces NO_SYSTEM_DIAGRAM: a workflow, dataflow or lifecycle diagram may stand beside the architecture diagram, no longer instead of it. The participant check (UNKNOWN_PARTICIPANT) therefore always has its reference. Before, a product could pass stages 1 and 2 with a workflow alone and meet the missing architecture diagram at stage 3, two checkpoints late. `draw_diagram_skill` R12, R17; design document § 5 stages 1 and 2, rules 17, 18 and 26; Appendix A.2. Origin: found verifying FB-38.

## [2.2.2] - 2026-10-23

A pull request that moves the framework pin needs a person's approval again.

### Migration

| Edit | Where | Required |
|---|---|---|
| Add `/.framework <owners>` and `/qf.yaml <owners>` next to `/.gitmodules` | the product's `.github/CODEOWNERS` (a code owner's change) | optional: the gate already requires the person; the lines make the host ask the code owners too |

### Fixed

- **Moving the framework pin is sampled.** *verify_delivery_reviewed_gate* guarded `.gitmodules`, which changes only when the submodule is added or its URL moves; a version move changes the submodule's commit at `paths.framework_dir` (`.framework`), so such a pull request merged on the reviewer agent's approval alone. The gate now guards both, and the setup's `CODEOWNERS` names the pin and `qf.yaml` as the gate does. Design document § 5 stage 9; QUICKSTART. Origin: FB-40 (wp_publisher); the `CODEOWNERS` gap found verifying FB-40.

## [2.2.1] - 2026-10-22

A corrected diagram, set of requirements or stack can be approved again.

### Fixed

- **A re-approval is no longer "too late".** The approval gates of checkpoints 1, 2 and 3 compared the latest approval with the first commit of the work derived from it, so once that work existed no approval could pass again, and rule 25's way back through checkpoint 1 and the v2.2.0 migration could not be completed. The order is now checked against the first approval at the checkpoint; a later one needs only to cover the current content. `tools/check_approval_order_tool.py`; design document § 5 stages 1 and 2, rule 25; Appendix A.2. Origin: FB-39 (wp_publisher).
- **A rebase no longer moves derived work later.** The order reads the commit's author date, which a rebase, amend or cherry-pick keeps, instead of the committer date, which they rewrite. Origin: found verifying FB-39.

## [2.2.0] - 2026-10-22

A sequence participant that is no part of the architecture diagram is found at stage 1, before the architect approves the diagrams.

### Migration

| Edit | Where | Required |
|---|---|---|
| Name every participant of a sequence diagram as the architecture diagram names that part, then approve the diagrams again at checkpoint 1 and the requirements at checkpoint 2 (§ 5 stages 1 and 2, rule 25) | the product's diagrams, only where *check_diagram_contract_gate* reports UNKNOWN_PARTICIPANT | required: stage 1 is a finished stage, so its finding fails CI |

### Changed

- **The participant check moved to stage 1.** *check_diagram_contract_gate* reports UNKNOWN_PARTICIPANT for a sequence participant that is no node of an architecture diagram, once one exists; *check_design_contract_gate* no longer checks it, so one mismatch is one finding. Before, the check waited for the first component, two stages after the diagrams were approved. `draw_diagram_skill` R17, `write_design_skill` R8; design document § 5 stages 1 and 2, rules 20 and 26. Origin: FB-38 (wp_publisher).

## [2.1.2] - 2026-10-21

The organization owner approves the reviewer agent's token against the permissions it really asks for.

### Fixed

- **QUICKSTART step 3, item 6 names the permissions of item 5.** It still asked the owner to approve "those two permissions" while item 5 grants four, or five with *Checks: read*, so a right request could be refused. Origin: FB-37 (wp_publisher).

## [2.1.1] - 2026-10-19

The reviewer agent's token can read CI, and is saved without a command that keeps it in the shell's history.

### Migration

| Edit | Where | Required |
|---|---|---|
| Give the reviewer agent's token *Commit statuses: read* and *Actions: read* (and *Checks: read* where offered), then check it with QUICKSTART step 3, item 7 | the reviewer-bot's token on GitHub | required: without them the reviewer cannot wait for green |

### Fixed

- **The reviewer agent's token reads CI.** QUICKSTART step 3, item 5 granted only *Pull requests* and *Contents*, so every read of CI answered 403 and the method's "wait for green" could not be done; it now adds *Commit statuses: read* and *Actions: read*, item 7 checks them, and the reviewer reads the head's *qf/merge* sign to wait for green (`derive_review_plugin` step 1, `run_reviewer_agent.md` § 1). Design document § 5 stage 9, rule 1. Origin: FB-36 (wp_publisher).
- **Saving the token needs no clipboard command.** The token is pasted into the file with an editor (`nano`, `notepad`), never typed into a command, so it never lands in the shell's history. QUICKSTART step 3, item 5. Origin: FB-35 (wp_publisher).

## [2.1.0] - 2026-10-19

Whoever merges reads on the pull request whether to wait or merge, and the reviewer agent's token is kept like an SSH key.

### Migration

| Edit | Where | Required |
|---|---|---|
| Copy the framework's `templates/github/quality_gates.yml` again: it adds `statuses: write`, the `concurrency` group and the two *Crossing sign* steps | `qf.yaml ci_file` (a code owner's change) | optional: without it no crossing sign is posted |
| Save the reviewer agent's token in `~/.aspice_agent_reviewer_bot_token/<owner>` (QUICKSTART step 3, item 5) and load it from there | each reviewer's machine | optional |

### Added

- **The crossing sign on every pull request.** CI posts the commit status `qf/merge` on the head with `post_merge_status_tool`: *Wait: gates running*, then *Wait: <what is missing>* — the reviewer agent's approval, a person's approval when sampled, the red gates — or *Ready to merge*. One run per pull request at a time; runs on main are never cancelled. QUICKSTART tells whoever merges to merge only on *Ready to merge*. Design document § 5 stage 9, rule 13; Appendix A.8. Origin: FB-33 (wp_publisher).
- **A home for the reviewer agent's token.** Like an SSH key: `~/.aspice_agent_reviewer_bot_token/<owner>` on macOS and Windows, one file per repository owner, readable only by the person, loaded into the reviewer's session with one line and read by no framework tool. Design document § 5 stage 9, rule 1; Appendix A.8. Origin: FB-34 (wp_publisher).

### Changed

- **Every stack area is described.** `choose_stack_skill` and the design document § 3 *The tech stack* list the 22 areas one per row: what each names, whether it can be not needed, and what the framework gives. Origin: internal.

## [2.0.0] - 2026-10-19

The tech stack lists every tool the product takes from outside, area by area, each chosen or not needed with the reason; how the product is tested moved to the verification plan; an accepted delivery that was right closes its non-conformance.

### Migration

| Edit | Where | Required |
|---|---|---|
| Rewrite the stack as `contract: stack.v2`: one row under `areas` per tool (`area`, `tool`, `version`, optional `purpose`), or `{area: <area>, not_needed: <reason>}`, for every area of `choose_stack_skill`; `version_control: GitHub`, `ci_cd: GitHub Actions`, `task_management: GitHub Issues`, and `requirements_engineering` / `diagram_tool` as the slots `create_requirements_plugin` / `create_diagram_plugin` name them, without a version | `paths.stack_file` | required: `check_stack_decision_gate` |
| Move `checks.lint`, `checks.format`, `checks.static-analysis` to the rows of the areas `lint`, `format`, `static_analysis` (`run`, `version_command`), `security_scans.secrets` / `.dependencies` to `secrets_scanner` / `dependencies_scanner` (with `results`); add a `test_runner` row with its `version_command` for each tool a suite runs with; keep `code_files`, `env_read_patterns`, `decision_record` | `paths.stack_file` | required |
| Move each suite of the stack's `suites` into the `suites` of its level's plan section — `unit` into `unit`, `integration` into `integration`, `software`/`e2e`/`bench`/`security` into `software`, `validation` into `validation` — with `tool` naming a `test_runner` row (no `version`, `version_command`), and `test_files` from `test_files`, `integration_test_files`, `software_test_files`, `validation_test_files` | `paths.verification_plan_file` | required where the plan exists: `check_verification_plan_gate` |
| Approve the stack again at checkpoint 3 | `paths.approvals_dir` | required where the stack was approved: `verify_stack_approval_gate` |

### Added

- **Every area of the stack, chosen or not needed.** `stack.v2`: one row per tool in its area; every stack holds 22 areas — language to diagram tool — each chosen with an exact version or marked not needed with the reason; language, test runner, lint, format and the two scanners always name a tool (MISSING_STACK_AREA, MISSING_REASON). A product may add its own areas. `check_stack_decision_gate`, `choose_stack_skill` R3; design document § 3 *The tech stack*, § 5 stage 3, rule 10; Appendix A.3. Origin: FB-32 (wp_publisher).
- **The areas the framework gives are rows of the stack.** Version control, CI/CD and task management name GitHub, GitHub Actions and GitHub Issues; requirements engineering and the diagram tool name the plugins of their slots (GIVEN_AREA_MISMATCH). `choose_stack_skill` R4. Origin: FB-32 (wp_publisher).
- **The stack as a table.** `write_stack_table_tool` prints *Area · Tool · Version · Status* for the checkpoint-3 request and the pull request; `derive_architecture_plugin` step 3. Origin: FB-32 (wp_publisher).

### Changed

- **The suite commands live in the verification plan.** Each plan section holds its level's `suites` (`tool`, `run`, `results`, `coverage`, `measurements`, `run_selected`, `selected_form`, `test_files`), written with that level's tests and agreed at the pull request; a suite's `tool` names a test runner of the stack, which gives its version (UNKNOWN_TOOL). UNKNOWN_INSTRUMENT moved from `check_stack_decision_gate` to `check_verification_plan_gate`, once the level's section exists. Findings about a suite point at the plan. The stack-file test-file patterns moved with their suites. Design document § 5 unit stages, rule 5. Origin: FB-31 (wp_publisher).
- **"Every suite runs in parallel" moved with the suites.** `run_verification_suites_skill` R11, judged at checkpoint 4. Origin: FB-31 (wp_publisher).
- **A contract is found by any version.** `validate_contract_tool` reads `<name>_contract.v<N>.schema.json`. Origin: internal.

### Fixed

- **An accepted delivery that was right can close its non-conformance.** Nothing was fixed, so it has no `fixed_by`: `check_nonconformances_gate` passes a closed non-conformance whose delivery a person in `urgent_approvers`, not the author of the pull request it names, accepted with `/accept-delivery`; `fixed_by` keeps naming a real fix — the change, a revert, the fix of a wrong gate. Before, the issue could neither close (NONCONFORMANCE_WITHOUT_FIX) nor stay open past `escalate_after_days` (UNESCALATED_NONCONFORMANCE). `track_nonconformances_skill` R1; design document § 5 stage 9, rule 12; Appendix A.8. Origin: FB-30 (wp_publisher).

## [1.8.0] - 2026-10-19

A change that reached the main branch without the delivery desk is accepted after the fact by a declared person, on the record; a re-run after the merge no longer counts.

### Migration

| Edit | Where | Required |
|---|---|---|
| For a change that reached `main` without the delivery desk (here #6, merged with red gates): open an issue labelled `non-conformance` with a `nonconformance` block naming it (`found_in: 6`) and the cause, and have a person in `urgent_approvers`, not its author, comment `/accept-delivery` on it | the product's issues | required before a release, where the gate reports one |

### Added

- **A delivery accepted after the merge.** A commit from no pull request, a pull request merged before its reviews, or one merged without a gates check that passed before the merge blocks the release until a non-conformance names it (`nonconformance.v1` `found_in`, or the new `commit` for a direct push) and a person in `urgent_approvers`, not its author, comments `/accept-delivery` on it. `verify_delivery_reviewed_gate`; `review_code_skill` R11, `track_nonconformances_skill`; design document § 5 stage 9, rule 12; Appendix A.8. Origin: FB-29 (wp_publisher).
- **After a merge the agent waits for the main branch's run** and reports one that is red at once, with the way out. `run_aspice_agent.md` step 6. Origin: FB-29 (wp_publisher).

### Changed

- **Only a gates check that finished before the merge counts.** A re-run after the merge reads an empty range — the head is on the main branch by then — so it proved nothing. `read_host_tool` reads each check's completion time and the merge time. Origin: found verifying FB-29.

### Fixed

- **"Until the change is reverted or reviewed" was not true.** A revert leaves the commit in the history the release checks, so it never cleared the finding. The gate's docstring and messages, stage 9 rule 6, BP6, Appendix A.8, the QUICKSTART and the CI template now name the way out. Origin: FB-29 (wp_publisher).

## [1.7.2] - 2026-10-19

A review's CI run reads only the pull request's commits, and the gates run in parallel.

### Migration

| Edit | Where | Required |
|---|---|---|
| Replace the `QF_BASE:` line with the template's: `QF_BASE: ${{ github.event.pull_request.base.ref && format('origin/{0}', github.event.pull_request.base.ref) \|\| '' }}` | the product's CI file (`.github/workflows/quality_gates.yml`), as in `.framework/templates/github/quality_gates.yml` | required — without it the run a review starts reads the whole history and fails on the setup commit |

### Fixed

- **The run a review starts reads only the pull request's commits.** `github.base_ref` is empty on a `pull_request_review` event, so the template passed no `QF_BASE` and the commit gate read the whole history, failing on the product's setup commit: an approved pull request never turned green. The template now takes the base from `github.event.pull_request.base.ref`, which both events carry, and without a base `read_commit_range_tool` also finds the remote's `main` or `master`, all a CI checkout has. Origin: FB-28 (wp_publisher).

### Changed

- **The gates run in parallel.** `run_gates_tool` runs the gates that only read at once and keeps the results in the order asked for; the gates that run the product's own commands (`RUN_ALONE`) run first, one at a time, since they write and keep those runs. A resolver call on a machine with 8 cores is about twice as fast. Origin: internal.

## [1.7.1] - 2026-10-18

The reviewer-bot's GitHub setup is written step by step, for a personal and an organization's repository, and a token that cannot read the repository says so.

### Migration

| Edit | Where | Required |
|---|---|---|
| For an organization's repository: make the reviewer-bot a member, create its token with the organization as resource owner and the repository selected, and have an owner approve it where the organization asks (QUICKSTART step 3, items 3–6) | the organization's settings and the reviewer-bot's account | required where the token cannot read the repository — the reviewer posts nothing until it can |

### Changed

- **The reviewer-bot's GitHub setup, step by step.** `QUICKSTART.md` step 3 now covers write access as a collaborator or an organization member, the organization's token policy, the fine-grained token's resource owner, repository and permissions, the owner's approval of the token, a check that the token reads the repository, its renewal, and the trade-off of the classic-token fallback. "Nothing else is configured on GitHub" now holds beyond those steps. Origin: FB-26 (wp_publisher).
- **The reviewer checks its token first.** `run_reviewer_agent.md` § 1 reads the repository with the token before the review, and sends the person to the QUICKSTART on a 404. Origin: FB-25 (wp_publisher).

### Fixed

- **A token that cannot read the repository is no longer reported as a missing pull request.** GitHub answers 404 for a private repository the token cannot see; `read_host_tool` now reports a pull request missing only when the repository itself reads, and otherwise raises "The token cannot read <repo>", naming the resource owner, repository list, permissions and the organization's approval. `post_review_tool` prints it; a gate reports it as HOST_UNREADABLE. Design document § 5 stage 9, rule 4. Origin: FB-25 (wp_publisher).
- **`read_host_tool`'s docstring** said a host that cannot be read crashes the gate (GATE_CRASHED); it fails closed with HOST_UNREADABLE since v1.7.0. Origin: found verifying FB-25.

## [1.7.0] - 2026-10-18

Tests are fast by design: CI runs every test on every change, within a time budget per level.

### Migration

| Edit | Where | Required |
|---|---|---|
| Delete `on_change` from the unit, integration and software sections | `paths.verification_plan_file` | required — `verification_plan.v1` no longer has the field, so the plan fails its contract until it is gone |
| Delete the `QF_RUN` line and the comment on selection from the CI file, as in `templates/github/quality_gates.yml` | `paths.ci_file` | recommended — CI no longer reads `QF_RUN=full`; every run is full |
| Run each suite in parallel in its stack command (e.g. `pytest -n auto`) | `paths.stack_file` | recommended — the suites must fit their time budget (`check_time_budget_gate`, from stage 6) |

### Changed

- **CI runs every test on every change.** `run_stack_commands_tool` runs every suite in full and keeps how long it ran; the selection by markers serves the coder's own loop, with `QF_RUN=selected`. The plan's `on_change` is gone. Design document § 5 unit stages, rules 30–32. Origin: internal.
- **A time budget per level** (new: `check_time_budget_gate`, at stages 6–8). The plan's sections may state a `time_budget`; without one the defaults apply: the unit suite 120 s and each unit test 0.5 s, the integration suite 300 s, the software suite 600 s. A suite over its budget (SUITE_OVER_BUDGET), a unit test over its own (TEST_OVER_BUDGET) and a looser budget without a reason (MISSING_BUDGET_REASON) fail. The verification report shows each suite's time and its slowest tests. Rule 33, Appendix A.5 *Fast by design*. Origin: internal.
- **Each level tests what a lower one cannot show.** `enforce_test_first_skill` R9, `verify_integration_skill` R9, `verify_software_skill` R10, the tester methods; `choose_stack_skill` R6 runs every suite in parallel. Origin: internal.
- **The framework's own tests follow the same strategy.** Four layers, each proving one thing once: static (`tests/consistency`, `tests/schema`, with a new check that every rule a gate reports has a unit test), unit (`tests/unit`, with the resolver's routing for every stage stood in), seam (`tests/seam`, every gate script run as a process on one complete product built once) and journey (`tests/journey`, formerly `tests/scenarios`: one happy walk per stage; the 33 negative cases are the gates' unit tests'). `tests/requirements-dev.txt` adds `pytest-xdist`; framework-ci runs the suite with `-n auto --dist loadfile`, reports its 25 slowest tests, and fails when the full suite runs over its budget of 420 s, about 1.4 times its slowest run on a CI machine (312 s). A full run took 21 minutes; it takes 3 to 5, on CI too. Origin: internal.

## [1.6.1] - 2026-10-18

Every pull request is reviewed by the reviewer agent from the first one on, in a session of its own, on a checklist of what the pull request holds.

### Migration

| Edit | Where | Required |
|---|---|---|
| Create the reviewer agent's token as a fine-grained token for the product's repository only, *Pull requests: read and write* and *Contents: read* (QUICKSTART step 3), and keep it out of the developer's session | the reviewer agent's account | recommended — a token in the developer's session lets the author's agent post the review itself |
| For each pull request the agent asks for a review, start a second session with the reviewer agent's token in `QF_HOST_TOKEN` and have it follow `.framework/agent/run_reviewer_agent.md` | the developer's machine | required — the pull request stays red with MISSING_AGENT_REVIEW until the reviewer approves its head |

### Changed

- **The reviewer agent reviews every pull request.** `run_aspice_agent.md` step 6 sends every pull request, at every stage, to the reviewer, not only stage 9's; the MISSING_AGENT_REVIEW finding names the next step. Design document § 5 stage 9, rule 1. Origin: FB-24 (wp_publisher).
- **The reviewer works in a session of its own** (new: `agent/run_reviewer_agent.md`). Only that session holds the reviewer agent's token, a token that can review and not push; the author's session never posts a review. `review_code_skill`, `derive_review_plugin`; rule 1, Appendix A.8. Origin: FB-24 (wp_publisher).
- **The checklist follows what the pull request holds.** `post_review_tool.required_items` asks for *logging* only when the pull request changes a file under `paths.code_dir`; the tool writes those items and `verify_delivery_reviewed_gate` checks those (INCOMPLETE_CHECKLIST). *Style* covers the names and conventions of documents too. `review_code_skill` R3, R7; rule 7. Origin: FB-24 (wp_publisher).

### Fixed

- **A host that cannot be read fails the gate closed, with a result.** A gate that reads the code host (`verify_delivery_reviewed_gate`, `verify_framework_integrity_gate`) ran as a script without a host stopped with a traceback; `run_gate_command_tool` now reports HOST_UNREADABLE in findings.v1 and exits 1. Design document § 5 stage 9, rule 4. Origin: found by the new seam test.
- **Two helpers no longer collected as tests.** `tools/select_tests_tool.py` `tests_argument` is now `selected_tests_argument`, and the SWE.6 scenario's `tested_without_the_plan` is now `the_bridge_tester_without_the_plan`: pytest collected both as tests by their *test* prefix, and they failed for want of fixtures. Origin: internal.

## [1.6.0] - 2026-10-17

The diagrams are reviewed on their pictures, the requirements on one page laid out to be read; an approval is never recorded on a stale page, and a changed diagram sends the requirements back for review.

### Migration

| Edit | Where | Required |
|---|---|---|
| Delete `review.html` and have checkpoint 1 approved again on the pictures | `paths.diagrams_dir` | required — the approval no longer covers that page, so the existing one reports APPROVAL_OUTDATED |
| Render the requirements' page again, `python .framework/agent/render_review_tool.py --root .` (the `--checkpoint` option is gone), commit it, and have checkpoint 2 approved again on it | `paths.requirements_dir` | required — REVIEW_PAGE_OUTDATED until rendered; an approval of checkpoint 2 now also covers the diagrams, so an existing one reports APPROVAL_OUTDATED |

### Changed

- **The diagrams are reviewed on their pictures.** The checkpoint 1 review page is gone: `verify_diagram_approval_gate` no longer asks for `<diagrams_dir>/review.html`, and the checkpoint 1 approval covers the diagrams and their pictures only. `draw_diagram_skill` R16. Origin: FB-20 (wp_publisher).
- **The requirements' page is laid out to be read.** `render_review_tool` renders the checkpoint 2 page only: each system-level requirement shaded, the software-level ones refining it indented under it; readable headers, every other field under *Details*; glossary terms in italics; each acceptance case coloured by its case; a threshold in bold. A changed row marks the removed and added words; a summary counts what is new, changed and removed, and can hide the rest. `write_requirements_skill` R16; design document § 5 stages 1 and 2, rules 22–23. Origin: FB-21 (wp_publisher).
- **No approval on a stale page.** `record_checkpoint_tool` refuses to record an approval at checkpoint 2 while the review page is missing or differs from what the files render now. Rule 24. Origin: FB-22 (wp_publisher).
- **A changed diagram sends the requirements back for review.** The checkpoint 2 approval also covers the diagrams the requirements are derived from (the specs, invariants and wish links), so a diagram change withdraws it; the review page names the diagram files changed since the previous approval. `write_requirements_skill` R17; rule 25, Appendix A.2. Origin: FB-23 (wp_publisher).

## [1.5.0] - 2026-10-17

CI checks every change by the rules that apply to it, and only for what it contains: the always-on gates run from the setup on, a finished stage stays enforced, the current stage is work in progress. At checkpoints 1 and 2 the person approves what they can read: the diagrams' pictures and a review page, committed and covered by the approval.

### Migration

| Edit | Where | Required |
|---|---|---|
| Replace the gates step with the template's two steps *Quality gates* and *Show the gates not run* | `.github/workflows/quality_gates.yml` | optional — the old step still runs the gates; the new one lists the gates not run in the run's summary |
| For every stage from 3 to 10 the product has already passed, record it as done: `python .framework/agent/record_stage_done_tool.py --stage <stage> --root .`, in order, and commit the records | `paths.approvals_dir` | required for a product past stage 3 — until then the resolver stops at the first such stage, as work in progress |
| Next to every diagram, commit the picture the diagram plugin renders from it, as `<id>.<type>.html` (for Archify, copy the page it writes under `.archify/`) | `paths.diagrams_dir` | required — stage 1 fails with MISSING_PICTURE |
| Render both review pages, `python .framework/agent/render_review_tool.py --checkpoint 1 --root .` and `--checkpoint 2`, commit them with the pictures, and have checkpoints 1 and 2 approved again on them | `paths.diagrams_dir`, `paths.requirements_dir` | required — stages 1 and 2 fail with MISSING_REVIEW_PAGE, then APPROVAL_OUTDATED until approved again |

### Changed

- **The always-on gates.** `verify_framework_integrity_gate`, `verify_required_checks_gate`, `check_framework_feedback_gate`, `verify_delivery_reviewed_gate`, `check_commit_conventions_gate` and `verify_history_kept_gate` moved out of stages 9 and 10 into `agent/stages.yaml always_gates`: they run on every pull request and every push to the main branch from the setup on, whatever stage the product is in. A pin, CI file or `qf.yaml` change needs a person's approval from the first pull request on. The two that read the code host (`host_gates`) run where one is configured — always in CI — and are listed as not run, reason *no_host*, without one. Design document § 5 *What CI fails on*, Appendix A.1. Origin: FB-12 (wp_publisher).
- **Only finished stages fail CI.** A stage is finished once its checkpoint has been approved, or, for a stage without a closing checkpoint, once its stage done record exists (`stage_done.v1`, written by the new `agent/record_stage_done_tool.py` when its gates first pass); breaking a finished stage fails CI. The current stage is work in progress: `resolve_stage_tool` reports its findings under `reported`, status *in_progress*, and CI does not fail on them; its checkpoint and the release still need them gone, and while a release is proposed every stage is enforced. A framework bump, a tooling or documentation change, a stage split over several pull requests and a checkpoint approval committed with its stage's work all pass. `run_aspice_agent.md` says when to record a stage and where an approval is committed. Origin: FB-13, FB-15 (wp_publisher).
- **Every gate not run is reported.** `not_run` lists each gate with its reason — *stage_not_reached*, *planned* or *no_host* — and the CI template prints the list in the run's summary. Origin: FB-12 (wp_publisher).
- **The person approves what they can read** (new: `agent/render_review_tool.py`). Every diagram keeps its picture, the page the diagram plugin renders, committed next to it with the diagram's last change or after it; `check_diagram_contract_gate` checks it by git's order of commits, so CI needs no plugin (MISSING_PICTURE, PICTURE_OUTDATED). Before checkpoints 1 and 2 the agent renders a review page with the new tool, never by hand: at checkpoint 1 every diagram's elements and wish links next to its picture, at checkpoint 2 each system-level requirement followed by the software-level ones refining it, with every field, and the glossary. What changed since the previous approval of the checkpoint is marked, read from git. The page depends only on the files and that approval's commit, so `verify_diagram_approval_gate` and `verify_requirements_approval_gate` render it again and compare byte for byte while it awaits approval (MISSING_REVIEW_PAGE, REVIEW_PAGE_OUTDATED). The approval covers the pictures and the page through the hashes it already holds; no new hash or receipt. `draw_diagram_skill` R15–R16, `write_requirements_skill` R16, `run_aspice_agent.md` steps 6 and 8. Design document § 5 stages 1 and 2, rules 21–25, and Appendix A.2. Origin: FB-18, FB-19 (wp_publisher).
- **Only failing attempts in a row count.** `count_retries_tool` ends a round at a passing attempt, so passing runs and changes asked for after a pass no longer use up the retry budget; the escalation report holds the attempts of the round. Origin: FB-14 (wp_publisher).

## [1.4.0] - 2026-10-16

Diagrams at two levels: the picture at a glance gives the system-level requirements, each feature's sequence diagram the software-level ones.

### Migration

| Edit | Where | Required |
|---|---|---|
| Draw at least one system-level diagram (architecture, workflow, dataflow or lifecycle) and at least one sequence diagram, and approve them again at checkpoint 1 | `paths.diagrams_dir` | required — stage 1 fails with NO_SYSTEM_DIAGRAM or NO_SEQUENCE_DIAGRAM |
| Link every behaviour wish to an element of a sequence diagram | `<diagram>.wishes.yaml` of the sequence diagrams | required — stage 1 fails with WISH_NOT_IN_SEQUENCE |
| Derive each system-level requirement from a system-level diagram and each software-level one from a sequence diagram; a step the sequence diagram details is derived there only | `paths.requirements_dir` | required for requirements already written — stage 2 fails with LEVEL_MISMATCH |

### Changed

- **Two levels of diagram.** A stage 1 diagram's type sets its level. A system-level diagram (architecture, workflow, dataflow, lifecycle) is the picture people read at a glance, and its nodes, edges and invariants give the system-level requirements. A sequence diagram, one per feature, holds the steps in detail, and its participants and invariants give the software-level requirements, each refining a system-level one, and its messages their acceptance criteria. A step is derived once, at the level that details it, so a flow drawn as a picture and as a sequence no longer doubles its requirements. `check_diagram_contract_gate` requires both levels (NO_SYSTEM_DIAGRAM, NO_SEQUENCE_DIAGRAM); `verify_diagram_to_wishes_link_gate` requires every behaviour wish in a sequence diagram (WISH_NOT_IN_SEQUENCE); `verify_requirements_to_diagram_link_gate` requires a requirement's level to be its diagram's (LEVEL_MISMATCH), which was checked only at checkpoint 2 before, and counts coverage per level. `draw_diagram_skill` R12–R14, `write_requirements_skill` R3 and R13, `derive_requirements_plugin` step 1. Design document § 5 stages 1 and 2, rules 17–20, and Appendix A.2. Origin: FB-16, FB-17 (wp_publisher).
- **The quick start names its roles reviewer, developer and reviewer-bot,** and says that three accounts are enough: one account fills the code owner, urgent approver and change approver. The README gives only the quick start's address. Origin: internal.

## [1.3.1] - 2026-10-15

A quick start for new teams, free branch names, and stages named by number.

### Migration

| Edit | Where | Required |
|---|---|---|
| Add the line `.archify/` | `.gitignore` | optional — keeps Archify's working folders out of git; a developer who excluded it in `.git/info/exclude` may drop that line |

### Added

- **The quick start.** `QUICKSTART.md` takes a new team from an empty folder to the ASPICE Agent's first stage: the person opens a coding agent in the folder and tells it to follow the file, and the agent checks the machine, explains the roles and the GitHub accounts, fetches the framework at its latest release, runs `agent/start_product.md`, has the first commit pushed and the diagram plugin Archify installed by the person, and hands over to `agent/run_aspice_agent.md`. Built from the pilot product's quick start. Origin: wp_publisher.

### Changed

- **The name is ASPICE Agent.** The README's title and the design document's title say ASPICE Agent, and the README opens with the agent's goal and philosophy. Origin: internal.

### Fixed

- **Any branch name but two is free.** `check_commit_conventions_gate` checks only the branch names that carry meaning — *arch/<slug>* for the architecture track and *release/v<version>* for a release (BAD_BRANCH_NAME); any other name is free, since every commit names its *REQ-<n>* or *#<n>*. Work that serves no requirement — tooling, documentation, a framework bump — now has a valid branch. Design document Appendix A.9. Origin: FB-10 (wp_publisher).
- **The setup ignores Archify's working folders.** `tools/create_product_tool.py` adds *.archify/* to `.gitignore`, next to *.qf/*, *.agents/* and *.claude/*; `QUICKSTART.md` no longer asks each developer to exclude it locally. Origin: FB-10 (wp_publisher).
- **A stage is named by its id or its number.** `load_skills_tool`, `run_gates_tool` and `count_retries_tool` take `--stage diagram` or `--stage 1`, one retry counter per stage either way; an unknown stage gets a one-line message listing the stages and exit 2, not a traceback. `agent/run_aspice_agent.md` says what `<stage>` is. Origin: FB-11 (wp_publisher).

### Removed

- **The migration path.** `Migration_Path.md` is gone: a team starts a new product with `QUICKSTART.md` instead of converting a product of the previous framework. Origin: internal.

## [1.3.0] - 2026-10-15

Nothing to configure on the code host: no admin token, no paid plan, no mirror. What happened is checked instead of how the host is set up, from two risk analyses.

### Migration

| Edit | Where | Required |
|---|---|---|
| Delete the `mirror:` line | `qf.yaml` | required — `qf.v1` no longer has the field, so the configuration is invalid until it is gone |
| Delete the step *Check the backup* | `.github/workflows/release.yml`, as in `templates/github/release.yml` | required — `verify_backup_gate` no longer exists |
| Add the `permissions:` block (`contents`, `pull-requests`, `checks`, `issues`: read) and set `QF_HOST_TOKEN: ${{ github.token }}` | `.github/workflows/quality_gates.yml`, as in `templates/github/quality_gates.yml` | optional — until then the old `QF_HOST_TOKEN` secret keeps working |
| Delete the repository secret `QF_HOST_TOKEN`, the branch protection rule and the mirror | The code host | optional — nothing reads them any more |

### Added

- **Every push to the main branch is checked after the fact.** `verify_delivery_reviewed_gate` (was `verify_host_settings_gate`) checks every commit a push adds: it came from a merged pull request (MERGED_WITHOUT_PULL_REQUEST) whose final head had its reviews and passed the gates check (GATES_NOT_PASSED, new); while a release is proposed, every commit since the last release. A pull request that changes the CI file, the framework pin or `qf.yaml` needs a person's approval. The commit that started the product is exempt. Design document § 5 quality assurance stage rules 2, 6 and 7. Origin: FB-4, FB-5, FB-7 (wp_publisher).
- **History, reasons and release tags checked with git.** `verify_history_kept_gate` (was `verify_branch_protection_gate`) requires every push to the main branch to keep the previous main branch in its history (MAIN_REWRITTEN, new); `check_commit_conventions_gate` checks the commits a push to the main branch adds; `verify_baseline_gate` requires every release tag to point to the commit where its record first appeared on the main branch (TAG_MOVED, new); the rulebooks forbid the agent to rewrite the main branch. Design document § 5 configuration management stage rules 7–10. Origin: FB-5 (wp_publisher).
- **`read_host_tool` reads the checks that passed on a commit** (`passed_checks`), with the token every CI run has. Origin: FB-4 (wp_publisher).

### Changed

- **`verify_required_checks_gate` reads no host.** It requires the CI job that runs the gates (MISSING_GATES_JOB, was CHECK_NOT_REQUIRED). Origin: FB-4, FB-5, FB-7 (wp_publisher).
- **The setup asks no mirror and prints no host steps.** `tools/create_product_tool.py` has no `--mirror`; it says nothing needs configuring on the host and that every developer keeps a clone with the framework submodule fetched. `agent/start_product.md`, the README and `Migration_Path.md` follow. Origin: FB-6, FB-7 (wp_publisher).
- **Two gates renamed for what they check.** `verify_branch_protection_gate` is `verify_history_kept_gate`; `verify_host_settings_gate` is `verify_delivery_reviewed_gate`. Origin: internal.
- **The risk analysis behind quality assurance.** Appendix A.8 records the stage's purpose — every released change reviewed and through every gate, every bypass detected on the main branch — its scenarios rated like configuration management's, and the decision: no paid plan, so the host's settings are not read; CI checks on every push to the main branch that each new commit came through a merged pull request whose final head passed the gates and had the approvals it needed, with a person's approval for a change to the CI file, the framework pin or *qf.yaml*; a finding blocks the release. D47 is superseded. Origin: FB-4, FB-5, FB-7 (wp_publisher).
- **The risk analysis behind configuration management.** Appendix A.9 of `docs/ASPICE_agent_documentation.md` records the stage's two purposes — code integrity with a backup, and traceability with the ability to revert — every scenario that endangers them rated 1–10 for occurrence, severity and detectability, and the decisions: a git check of the release tags (S3), of every commit on the main branch (S8) and of every push to it, which must keep the previous main in its history, with the rulebooks forbidding agents to rewrite it (S1); the loss of the repository (S4) or of the framework repository (S10) accepted, the developers' clones being the copy; configuration outside git, rebuilding old releases and compromised accounts out of scope. Origin: FB-4 to FB-7 (wp_publisher).

### Removed

- **The mirror.** `verify_backup_gate`, the `qf.v1` field `mirror`, the setup's `--mirror` and the mirror step of `release.yml`: losing the repository or the framework repository is an accepted risk, the developers' clones being the copy (Appendix A.9). Origin: FB-6 (wp_publisher).
- **Reading the host's settings.** The rule IDs BRANCH_NOT_PROTECTED, PROTECTION_BYPASSABLE, UNOWNED_PATH, FORCE_PUSH_ALLOWED, DELETION_ALLOWED and TAG_NOT_IN_MIRROR, and the branch-protection read of `read_host_tool`. Origin: FB-4, FB-5 (wp_publisher).

## [1.2.0] - 2026-10-15

Regression by traceability: on a change, only the tests traced to it run, and a full run on the release commit backs every selection.

### Migration

| Edit | Where | Required |
|---|---|---|
| Add `on_change: selected` (or `all`) to the unit, integration and software sections | The verification plan (`paths.verification_plan_file`) | required — `check_verification_plan_gate` fails until it is there |
| Add `run_selected` (with `{tests}`) and `selected_form` (`paths` or `names`) to the unit, integration and software suites | The stack (`paths.stack_file`), approved again at checkpoint 3 | optional — without them every test runs, as before |
| Move `QF_BASE` to the job's `env`, and add the `workflow_dispatch` trigger with `QF_RUN` | `.github/workflows/quality_gates.yml`, from `templates/github/quality_gates.yml` | optional — the selection then uses the same base in the report step and the gates |

### Added

- **Regression by traceability.** `tools/select_tests_tool.py` follows each changed file — the commits since `QF_BASE` and the uncommitted ones — through its `@unit`, `@component`, `@flow` and `@sdoc` markers, grows the scope along the architecture (a unit's component, the components joined to it by an interface, the requirements they meet, the flows they take part in) and selects the unit, integration and software-level tests in that scope, each with its reasons. A change that traces to nothing, nothing changed since the base, a proposed release and `QF_RUN=full` run every test. `tools/run_stack_commands_tool.py` runs a suite's `run_selected` with `{tests}` filled in, or nothing when no test is traced; the verification report lists what ran and why. Design document § 5 unit stages rules 30–33, stage 7 rule 14, stage 8 rule 11. `tests/unit/test_select_tests_tool.py`. Origin: internal.

### Changed

- **The gates judge a selected run by what it covers.** On a selected run a test that was not selected is not missing, and every selected test must pass. `check_stack_commands_gate` judges coverage, and `check_env_config_gate` the tests of required variables, on full runs only; `verify_tests_to_requirements_link_gate`, `verify_security_tests_gate`, `verify_nfr_thresholds_gate`, `verify_tests_to_components_link_gate`, `verify_tests_to_flows_link_gate`, `verify_log_events_gate` and `verify_software_tests_to_requirements_link_gate` check the units, components, flows, interfaces and requirements the run covers. Origin: internal.
- **The contracts hold the selection.** `stack.v1` suites may declare `run_selected` and `selected_form`; `verification_plan.v1` requires `on_change` in the unit, integration and software sections. The rulebooks `run_verification_suites_skill`, `choose_stack_skill`, `enforce_test_first_skill`, `verify_integration_skill` and `verify_software_skill`, the methods that write the plan, and `templates/github/quality_gates.yml` follow. Origin: internal.

- **The design describes regression by traceability.** On a change, only the tests traced to it run — the tests carrying the changed file's `@unit`, `@component`, `@flow` or `@sdoc` markers, every test when a change traces to nothing — and a full run on the release commit backs every selection. `docs/ASPICE_agent_documentation.md` § 4.1 SWE.4 BP2, SWE.5 BP3, SWE.6 BP2; § 5 unit stages rules 30–33, stage 7 rule 14, stage 8 rule 11; Appendix A.5 records the decision and when a heavier model pays off. Origin: internal.
- **The design document is `docs/ASPICE_agent_documentation.md`.** It was `docs/Quality_framework_documentation.md`; its content is unchanged. The README, `plugins/README.md` and the consistency tests name the new file. Origin: internal.

## [1.1.1] - 2026-10-15

The construction site setup tells the truth when it stops, keeps a feedback log, and says what to do with a folder git does not trust.

### Migration

| Edit | Where | Required |
|---|---|---|
| None | — | — |

### Added

- **The migration path.** `Migration_Path.md` takes a product from the previous framework to this one when its Archify diagrams exist and its requirements are started: remove the old submodule, keep the old work in `docs/legacy/`, set up with `tools/create_product_tool.py`, add the wishes, invariants and wish links, approve the diagrams at checkpoint 1, then convert the requirements and the glossary to their contracts under new file names, so `verify_diagram_approval_gate` does not find the approval late. Origin: internal.

### Changed

- **The framework's CI runs once per change, and only what the change needs.** `.github/workflows/framework-ci.yml` runs on a push to main and on pull requests, no longer again for a release tag; a new push to a pull request cancels the run it replaces. A change only to `docs/` or to root Markdown files runs the consistency tests, the only ones that read them; any other change runs the full suite, and `gh workflow run framework-ci` starts a full run by hand before a release is tagged. Origin: internal.
- **The contract examples name the framework's own methods.** The method slots in `contracts/examples/qf/valid/qf.yaml` and the twelve invalid samples named Gentle-AI's retired SDD skills (`gentle-ai/sdd-spec`, `sdd-design`, `sdd-apply`, `sdd-verify`); they now name `quality-framework/derive_*_plugin`, as `examples/login-product/qf.yaml` does. `tests/unit/test_read_product_config_tool.py` reads the new value. Origin: internal.

### Fixed

- **A refused setup leaves nothing behind.** `tools/create_product_tool.py` exited 2 — "nothing was changed" — after its `git init` had run, when a later git step failed, leaving a partial `.git/`. A failing git step now removes the repository the run created; a repository the person made is left as it was. `tests/unit/test_create_product_tool.py`. Origin: FB-1 (wp_publisher).
- **The setup keeps an existing feedback log.** It refused to run while `FRAMEWORK_FEEDBACK.md` existed, so a weakness met during the setup could not be recorded and the setup run again. It now keeps the log and its entries, and says so; `agent/start_product.md` records such a weakness before going on. Origin: FB-2 (wp_publisher).
- **A folder another account owns is caught before any change.** git refuses such a folder ("dubious ownership") unless its `safe.directory` names it. The setup now checks the owner first and names both accounts and the two ways on — run it as the owner, or the `git config --global --add safe.directory` command the person runs; `agent/start_product.md` relays them. Design document § 5 *Starting a product* rule 5, Appendix A.13. Origin: FB-3 (wp_publisher).

## [1.1.0] - 2026-10-13

Starting a product: the construction site setup and the start rulebook.

### Migration

| Edit | Where | Required |
|---|---|---|
| None | — | — |

### Added

- **The construction site setup.** The product is the repository's root and the framework its git submodule at `.framework`, checked out at a release tag. The person clones the framework at a release into the product folder; `tools/create_product_tool.py`, run from that clone, makes the folder a git repository if it is none, adopts the clone in place as the submodule with its `origin` as the URL, writes the product's `qf.yaml`, copies the CI workflows and the framework feedback log from `templates/`, writes a `CODEOWNERS` for the CI file, `.gitmodules` and the architecture folder, adds the agent's `.gitignore` lines and stages the submodule's release pin. It refuses to run from a framework copy outside the product, so the framework exists once. Every value only a person knows — reviewer agent, urgent and change approvers, code owners, mirror — is a required argument, never a placeholder. It checks everything before changing anything, never overwrites a file, commits nothing and never changes the code host: it prints the host steps the gates check. Or the person tells the agent to follow `agent/start_product.md`: it asks the values, runs the same command, relays the host steps, commits with the person's approval and hands over to `run_aspice_agent.md`; `tests/consistency/test_start_product.py` keeps its questions in step with the tool's required flags. Design document § 5 *Starting a product*, Appendix A.13. `tests/unit/test_create_product_tool.py`. Origin: internal.

## [1.0.0] - 2026-10-12

The first release: all 13 stages of the ASPICE Agent built.

### Migration

| Edit | Where | Required |
|---|---|---|
| None — first release | — | — |

### Added

- **WP0 contracts for the SWE.1 slice.** `contracts/` holds seven JSON Schemas — `requirement.v1`, `diagram.v1`, `invariants.v1`, `glossary_term.v1`, `qf.v1`, `approval.v1`, `findings.v1` — each with valid and invalid examples. `tests/schema/test_contracts.py` checks that every valid example passes and that every invalid one fails at the JSON path and keyword its `expect.yaml` names. Requirements are stored as fenced `yaml requirement` blocks in Markdown and point at diagram elements as `<diagram>#<id>`; main's `DERIVED_FROM` named only the element kind, so no gate could check the link. `diagram.v1` is the element list the framework's adapter produces from Archify's JSON; invariants, which Archify cannot express, live in `invariants.v1` next to each diagram. Nothing reads the contracts yet: the SWE.1 skills, gates and agent come next. Origin: internal.
- **The SWE.1 framework skills, written as contracts and rules.** `skills/swe/` holds `write_requirements_skill`, `define_glossary_terms_skill` and `specify_nfr_measurement_skill`, replacing main's `requirements-authoring`, `domain-glossary` and `nfr-measurability` (which stay until the cutover). Each names its contract and gates; every rule names the gate and rule ID, or the checkpoint, that checks it. `tests/consistency/test_skills.py` checks that structure and validates every example in a skill against its contract. `requirement.v1` now requires a number in `threshold` and a `qf.yaml` command name as `measurement_method.instrument`, as main's `nfr-measurability` did. Origin: internal.
- **The next major version is built as a self-contained tree.** It is developed under `Refactoring/` in main's repository, with its own documentation, changelog, tests and CI, and replaces main's tree at the cutover. Origin: internal.
- **Domain terms are marked `_term_` in requirements.** Statements and acceptance criteria write every domain term between underscores, so `check_glossary_gate` can detect an undefined term (`UNDEFINED_TERM`) and a glossary term left unmarked (`UNMARKED_TERM`); main's `check-glossary.sh` could detect neither. Underscores, not asterisks: a YAML value starting with `*` is an alias. Origin: internal.
- **A constraint requirement may derive from a customer wish.** `derived_from` accepts `W-<n>` for kind `constraint` only, so a given such as *must run on Java 21* records its real origin; every other kind still derives from a diagram element. Origin: internal.
- **The tech stack is a work product of SWE.2: `stack.v1`.** Language, runtime, frameworks, libraries, data stores, one command per verification suite and the coding-principle checks, every version exact, plus the decision record; approved by the architect at the new checkpoint 3. `qf.v1` loses its `stack` section; `approval.v1` has five checkpoints; a requirement's `instrument` names a suite (`unit`, `integration`, `software`, `bench`, `security`, `e2e`), never a tool, so it stays true whichever stack wins. Origin: internal.
- **A screaming tree, and names without hyphens.** The top-level directories are the framework's kinds — `agent/`, `skills/`, `gates/`, `adapters/`, `tools/`, `contracts/` — plus `examples/`, `docs/` and `tests/`. Every file carries its entity's name (`check_glossary_gate.py`, `read_archify_diagram_adapter.py`, `requirement_contract.v1.schema.json`); one file per gate replaces grouping gates by data source. Names use underscores only — first word the action, last word the kind — so they are valid Python module names and spelled the same everywhere. Gates, adapters and agent tools are written in Python. Origin: internal.
- **The three tools every gate builds on.** `tools/read_yaml_blocks_tool.py` reads the fenced YAML blocks of a Markdown file with the line of the block and of each field, and returns a broken block with its error instead of skipping it; `tools/validate_contract_tool.py` checks a record against `contracts/<name>_contract.v1.schema.json` and returns the violations in a fixed order; `tools/emit_findings_tool.py` prints a gate result in `findings.v1`, validated against the contract before it is printed, and returns exit code 0 or 1. Ruff (lint and format) joins pytest as the bar for this tree. Origin: internal.
- **The Archify adapter.** `adapters/read_archify_diagram_adapter.py` translates an Archify JSON spec — architecture, sequence, workflow, dataflow or lifecycle — plus its `<diagram>.invariants.yaml` into the element list of `diagram.v1`, with the source line of every element. An element without an ID, a label or an endpoint, or with an ID used twice, is reported in the findings shape and left out, never invented; the output is validated against `diagram.v1` before it is returned. Runs as a command or as a library. Origin: internal.
- **Wishes contract and the shared configuration reader.** `wish_contract.v1` (one ```yaml wish block per wish: id W-<n>, statement, source) and `qf.v1 paths.wishes_file`; `tools/read_product_config_tool.py` reads and validates `qf.yaml` and resolves every path under the product root, so gates never depend on the agent. The SWE.1 skills' rule IDs follow the slice decisions: observability is checked per sequence diagram, and the one-level refines tree replaces SELF_REFINES and REFINES_CYCLE with PARENT_NOT_SYSTEM. Origin: internal.
- **The three SWE.1 gates.** `check_requirements_contract_gate` (the contract per block, unique UIDs, the one-level refines tree, every system requirement refined, an observability requirement per feature), `check_glossary_gate` (marked terms defined, glossary terms always marked, no alias, no duplicate, no unused term) and `verify_requirements_to_diagram_link_gate` (every derived_from resolves to a diagram element or a wish; every node, edge and invariant covered). Each runs as `python gates/swe/<gate>.py --root <product>`, prints `findings.v1` and exits 0, 1 or 2; a missing or invalid `qf.yaml`, no requirements, no glossary or no diagrams fail closed. Cross checks use every readable block, so one broken field gives one finding, not a cascade. Shared pieces: `tools/read_requirements_tool.py`, `tools/run_gate_command_tool.py`; tests build a complete product with `tests/product_builder.py`. Origin: internal.
- **An example product at the start of SWE.1.** `examples/login-product/` has its wishes, two Archify diagrams with invariants, the checkpoint-1 approval bound to the diagrams' SHA-256, the glossary and `qf.yaml`. Its method slots are filled by a stand-in plugin, `examples/example-method/`, because Gentle-AI has retired its SDD skills upstream. Three scripted plugin outputs (`tests/scenarios/plugin_outputs/`) stand in for the method: correct, broken but fixable, stuck. Origin: internal.
- **The minimal ASPICE Agent.** `agent/stages.yaml` is the stage manifest (all 12 stages; stage 2 implemented). Six deterministic tools: `read_config_tool` (pipeline preconditions: `qf.yaml` valid, every slot's skill found on the machine), `resolve_stage_tool` (the first stage not done, from disk alone; planned gates reported as not run), `load_skills_tool` (the slot's plugin plus the stage's framework skills), `run_gates_tool` (each gate as a command; a missing or crashing gate fails closed), `count_retries_tool` (first run plus 3 retries logged under `.qf/attempts/`, then an escalation report with every attempt's findings) and `record_checkpoint_tool` (approval.v1 bound to the files' SHA-256; the latest decision counts while the files are unchanged). `agent/run_aspice_agent.md` is the orchestrator, the only LLM part, and decides nothing a tool can decide. Origin: internal.
- **The SWE.1 slice runs end to end.** `tests/scenarios/test_swe1_slice.py` drives the orchestrator's loop on a copy of the example product with scripted plugin outputs: a pass that moves on after checkpoint 2, a broken requirement fixed by a retry, a stuck one escalated after 3 retries, changes requested at checkpoint 2, and an edit that withdraws an approval. `templates/github/quality_gates.yml` is the product's CI: it refuses to run without a pinned framework commit, checks the preconditions, and runs the gates of every stage the product has reached (`resolve_stage_tool --check`). Origin: internal.
- **The method skill standard.** Every method skill — the *how* of a stage, filling its slot — follows one schema: front matter, title `# plugin: <name>`, header Stage · Fills slot · Loaded with (matching `agent/stages.yaml`), and seven sections — Goal, Explore, Ask, Depth, Steps, Changes, Done — with Done stating that completeness wins over a budget. `plugins/README.md` is the skeleton; `tests/consistency/test_plugins.py` enforces the standard and checks itself on a valid and eleven invalid samples. The schema takes the best of Gentle-AI 2.3.0's SDD skills, OpenSpec and the framework, follows ODD, and uses no provider-specific tool. Origin: internal.
- **Acceptance criteria state their case.** `requirement.v1` requires `case: happy | edge | error` on every criterion; `check_requirements_contract_gate` requires a happy case in every requirement (MISSING_HAPPY_CASE) and an edge or error case in every high-criticality one (MISSING_ERROR_CASE). Origin: internal.
- **Rules skills carry front matter.** `name` and `description` above the title of every rules skill, as method skills already had, so an Agent Skills host recognises them — the reason the `SKILL.md` layout was kept. `tests/consistency/test_skills.py` requires it. Origin: internal.
- **The SWE.1 method skill.** `plugins/swe/derive_requirements_plugin/SKILL.md` — the framework's own method for the requirements stage, replacing the stand-in: explore the approved diagrams, wishes, glossary and existing requirements; a question round before writing; lite or full depth by risk; one task per diagram element with happy, edge and error cases, the gates as the evidence a task is done; existing requirements grown, never rewritten. Learned from Gentle-AI 2.3.0's `sdd-explore`, `sdd-propose` and `sdd-spec` and from OpenSpec; follows ODD. Origin: internal.
- **Built-in methods.** A slot may name `quality-framework/<method>`: the preconditions resolve it from the framework's `plugins/`, so nothing needs installing; an unknown name is UNKNOWN_FRAMEWORK_PLUGIN. Origin: internal.
- **The orchestrator carries ODD's common steps.** `agent/run_aspice_agent.md` now runs Authorize (questions change nothing; work only on the stage that is due), Classify (small, substantial, change), Track before write (`.qf/tasks/<feature>.md` before the first file, read first on resume) and Close (verified outcome, failed and not-run checks, open assumptions, next step) around the existing steps. `tests/consistency/test_orchestrator.py` checks these sections, that every tool it runs exists, and that it uses no provider-specific tool. Origin: internal.
- **The example uses the framework's own SWE.1 method.** `examples/login-product` fills `create_requirements_plugin` with `quality-framework/derive_requirements_plugin`; the stand-in `specify` skill and its lockfile entry are removed, and the stand-in keeps only the stages whose method is not written yet. The SWE.1 scenario runs with the real method loaded. Origin: internal.
- **Findings of the first real run, applied.** A missing plugin's precondition finding says where the skill was looked for and how to declare its location; the question round is one message with an assumption per question; behaviour wishes enter through the diagram, only constraints derive from a wish; new domain terms are the method's terms step to mark; one behaviour per requirement is a rule of `write_requirements_skill`, confirmed at checkpoint 2. Origin: found running the agent on the example product.
- **Plugins are tools on the person's machine, found through an environment file.** A plugin may be installed for one project, one user or system-wide; it is never part of the product, and the person installs it — the framework never does, and `tests/consistency/test_orchestrator.py` fails if the orchestrator ever runs an install. The new contract `environment.v1` (`.qf/environment.yaml` for a project, else `~/.config/quality-framework/environment.yaml`, never committed) declares skill folders and individual plugin paths; without it the conventional folders (`.agents/skills`, `.claude/skills`, under the product and under `~`) are searched. A skill found nowhere is PLUGIN_NOT_INSTALLED, naming where it was looked for; an invalid file is INVALID_ENVIRONMENT. Plugin versions are not tracked — the gates prove the work product, whatever produced it — so `skills-lock.json` (vercel-labs' `npx skills` lockfile) is removed and `qf.yaml` pins nothing. CI needs no plugin, since the gates use none. Tests run with an empty temporary home directory. Origin: internal.
- **Diagrams link to wishes.** New contract `diagram_wishes.v1`: `<diagram>.wishes.yaml` next to each diagram maps its elements to the wishes they realise, and checkpoint 1 approves it with the diagram and its invariants. `wish.v1` gains an optional `kind`: a `constraint` wish (a runtime, a database) is exempt from diagram coverage and becomes a constraint requirement at SWE.1. The example product links its two diagrams to W-01 and W-02 and re-records its checkpoint-1 approval over the new file set. Origin: internal.
- **The diagram stage's rules skill.** `skills/swe/draw_diagram_skill/SKILL.md`: an ID and a label on every element, every flow connected, no orphan node, rules in the invariants file, wish links in the wishes file, every behaviour wish realised, and the architect's approval before requirements are derived — each rule naming its gate rule or checkpoint 1. Archify fills the slot, so the framework writes no diagram method. The approval logic moved from the agent into `tools/read_approvals_tool.py` so gates can share it. Origin: internal.
- **The diagram stage's gates; stage 1 implemented.** `check_diagram_contract_gate` (the adapter's problems, DANGLING_ENDPOINT, ORPHAN_NODE, UNKNOWN_CONSTRAINED_ELEMENT, NO_DIAGRAMS), `verify_diagram_to_wishes_link_gate` (every behaviour wish realised; links name existing elements and wishes) and `verify_diagram_approval_gate` (once requirements exist, a current checkpoint-1 approval dated before the first requirement was derived, from git history; NOT_A_GIT_REPOSITORY otherwise). `agent/stages.yaml` marks stage 1 implemented, so the resolver runs these gates. `verify_requirements_approval_gate` stays planned: with no design stage yet it could only pass without checking. Origin: internal. A new scenario shows that changing an approved diagram sends the product back to stage 1.
- **The architecture stage's contracts.** `component.v1` (```yaml component: the diagram node it comes from, responsibility, resource budget with value and unit, the requirements it meets; external actors marked and exempt), `interface.v1` (```yaml interface: the diagram edge, from and to, external or internal, protocol, data) and `decision.v1` (```yaml decision in `NNNN-<slug>.md`: at least two options with pros and cons, the choice, consequences). `qf.v1` gains `architecture_dir`, `decisions_dir` and `stack_file`. Origin: internal.
- **The architecture stage's rules skills.** `choose_stack_skill` (stack.v1: exact versions, a command for every suite a requirement names, a decision record, approval at checkpoint 3 before components), `write_design_skill` (one component per node and one interface per edge of the architecture diagram, budgets, every software requirement met) and `record_decisions_skill` (at least two options, the choice among them, superseding instead of rewriting) — each rule naming the gate rule the stage's gates will emit, or its checkpoint. Origin: internal.
- **The architecture method.** `plugins/swe/derive_architecture_plugin/SKILL.md`, the framework's own method for stage 3, written to the method standard: the stack first, stopped for checkpoint 3, then components, interfaces and decisions. From Gentle-AI 2.3.0's `sdd-design` it reuses three ideas: a threat table for every external interface (applicable with mitigation and test, or N/A with the reason), following the patterns the product already uses, and a migration for every change. Origin: internal.
- **The architecture stage's gates.** `check_stack_decision_gate` (the stack exists and follows stack.v1, its decision record exists, every suite a requirement names has a command), `verify_stack_approval_gate` (once architecture files exist, a current checkpoint-3 approval of the stack and its decision record, dated before the first architecture file), `check_design_contract_gate` (components and interfaces follow their contracts; one component per architecture-diagram node and one interface per edge; interfaces connect existing components and are external exactly when one end is; every software requirement met; only existing requirements and decisions named) and `verify_decision_records_gate` (one decision per record, file named after its ID, unique IDs, the choice among the options, superseded records exist). The approval-order check is shared with `verify_diagram_approval_gate` in `tools/check_approval_order_tool.py`. Origin: internal.
- **Stage 3 implemented, with a checkpoint inside it.** `agent/stages.yaml` runs the architecture stage's gates; checkpoint 3 approves the stack before any component is designed, so the stage's gates are split: `gates` (stack and decision records) always, `gates_after_checkpoint` (stack approval order, design contract) only while the checkpoint-3 approval is current. `resolve_stage_tool` walks stack missing → stack awaiting checkpoint 3 → components missing → done; `run_gates_tool --stage` runs the gates the stage has reached. `check_track_rule_gate` stays planned. Origin: internal.
- **The architecture stage runs end to end.** `tests/scenarios/test_swe2_architecture.py` continues from approved requirements on a copy of the example product: the stack waits for checkpoint 3, a passing design moves the product to stage 4, a broken design is fixed by a retry, changes requested at checkpoint 3 keep it waiting with no component, and a stack changed after approval withdraws it. Scripted plugin outputs now sit under `tests/scenarios/plugin_outputs/requirements/` and `…/architecture/`, the latter in the product's own layout. The example product fills its architecture slot with the built-in `quality-framework/derive_architecture_plugin`. Origin: internal.
- **`verify_requirements_approval_gate`, no longer planned.** Once the stack or an architecture file exists, the latest checkpoint-2 decision must approve the current requirements and glossary, dated before the first of those files (from git history); it runs with stage 2's gates, so editing a requirement after the design started sends the product back to stage 2. Code joins the derived files when stage 4 exists. Origin: internal.
- **The detailed design stage's contract.** `unit.v1` (```yaml unit in `<component-id>.md`, one file per component: the node of the component's design diagram it comes from, responsibility, inputs and outputs, the units of the same component it calls). Every input and output has a type, a range and a unit of measure: a `{min, max}` range needs a real unit, `not applicable` needs `not applicable`. `qf.v1` gains `detailed_design_dir`. SWE.3 BP1 and BP2 now say the design diagrams are agreed at the pull request rather than approved: no checkpoint approves a detailed design. `agent/stages.yaml` puts the code in stage 5, after its failing test: stage 4 is the detailed design (SWE.3 BP1–BP2), stage 5 is SWE.3 BP3 + SWE.4, so test first holds; the stage table and the flow diagram say the same. The detailed design gets its own gate, `check_detailed_design_contract_gate` (planned for stage 4), instead of a second scope inside `check_design_contract_gate`. Per component the design is `<component-id>.md` with `<component-id>.architecture.json` (the units) and `<component-id>.sequence.json` (the interactions), drawn by the diagram plugin; unit IDs are unique in the product. Origin: internal.
- **The detailed design stage's rules skill.** `write_detailed_design_skill`: per component a design file and its design diagrams, every unit from a node of its own component's structure diagram, unit IDs unique in the product, calls inside the component, ranges with min not above max, calls and sequence messages that agree both ways, and calls and structure-diagram edges that agree both ways — each rule naming the `check_detailed_design_contract_gate` rule ID it will emit, or checkpoint 4. Stage 4 loads the diagram plugin with it, not `draw_diagram_skill`, whose wishes, invariants and approval rules belong to stage 1. `draw_diagram_skill`'s example names the renamed login participants. Origin: internal.
- **The detailed design method.** `plugins/swe/derive_detailed_design_plugin/SKILL.md`, the framework's own method for stage 4, written to the method standard: read the architecture, the requirements and the existing code first (the one part taken from Gentle-AI's sdd-design); per component the units, their inputs and outputs with range and unit of measure, the calls inside the component, then the structure and sequence diagrams asked of the diagram plugin; IDs never reused. `agent/stages.yaml` loads `write_detailed_design_skill` at stage 4. Origin: internal.
- **`check_detailed_design_contract_gate`.** Per component of the architecture its design file and design diagrams: NO_DETAILED_DESIGN (fails closed), MISSING_DETAILED_DESIGN, UNKNOWN_COMPONENT, UNREADABLE_BLOCK, SCHEMA_VIOLATION, DUPLICATE_ID across the product, MISSING_DESIGN_DIAGRAM (the structure diagram always, the sequence diagram once a unit calls another), the adapter's problems, DANGLING_ENDPOINT, UNKNOWN_ELEMENT and UNCOVERED_NODE (units ↔ the component's own structure nodes), UNKNOWN_UNIT, INVALID_RANGE, UNKNOWN_PARTICIPANT, UNSHOWN_CALL and UNDECLARED_CALL (a reply to a call is allowed), UNDRAWN_CALL and UNDECLARED_EDGE (no replies among structure edges). `verify_requirements_approval_gate` counts detailed-design files among the derived ones. The test product gains a baseline detailed design (`detailed_design_doc()`). Origin: internal.
- **Stage 4 implemented, with a second plugin.** `agent/stages.yaml` runs `check_detailed_design_contract_gate` at stage 4 and gains `also_slots`: stage 4 lists `create_diagram_plugin`, and `load_skills_tool` returns it under `also_plugins` next to the slot's method, which the orchestrator reads too. The preconditions already check every slot's plugin is installed. A complete architecture now moves the product to stage 4, where NO_DETAILED_DESIGN waits for the method. Origin: internal.
- **The detailed design stage runs end to end.** `tests/scenarios/test_swe3_detailed_design.py` continues from a passing architecture on a copy of the example product: the method and the diagram plugin are loaded; a passing design moves the product to stage 5; a broken one (INVALID_RANGE, UNSHOWN_CALL) is fixed by a retry; one that stays broken escalates after 4 attempts. Scripted outputs in `tests/scenarios/plugin_outputs/detailed_design/`; the example product's `create_detailed_design_plugin` names `quality-framework/derive_detailed_design_plugin`. Origin: internal.
- **The unit construction and verification stage's contracts.** `verification_plan.v1` (one ```yaml verification_plan block in `paths.verification_plan_file`): the unit section's techniques, pass/fail, entry and exit criteria, infrastructure, selection, regression and minimum coverage (lines or branches, 0–100 %). `stack.v1` gains `test_files` (globs that tell a test from code) and, per suite, `results` (JUnit XML); the unit suite also requires `coverage` (Cobertura XML). `qf.v1` gains `code_dir` and `verification_plan_file`, and stage 5's one slot `create_unit_tests_and_code_plugin` becomes two, `create_unit_tests_plugin` (unit tests and stubs, without the code) and `create_unit_code_plugin` (the units); `agent/stages.yaml` splits stage 5 into stage 5 *unit_tests* (the tester) and stage 6 *unit_construction* (the coder); the later stages move one up, 13 in all. `choose_stack_skill` shows the new stack fields. Origin: internal.
- **The rulebooks of stages 5 and 6.** `enforce_test_first_skill` (stage 5, again at 6): the verification plan's unit section, a stub and tests per unit in one test-only commit per component, the red run, no unit code before its test, no test changed afterwards (rule IDs MISSING_VERIFICATION_PLAN, MULTIPLE_PLANS, MISSING_STUB, MISSING_UNIT_TEST, CODE_IN_TEST_COMMIT, RED_RUN_WITHOUT_RESULTS, TEST_NOT_FAILING, CODE_BEFORE_TEST, TEST_CHANGED_WITH_CODE). `construct_units_skill` (stage 6): unit markers in both directions, the component folder, requirement markers (MISSING_UNIT_MARKER, UNKNOWN_UNIT, UNIMPLEMENTED_UNIT, UNIT_OUTSIDE_COMPONENT, UNKNOWN_REQUIREMENT). `run_verification_suites_skill` (stage 6): pinned tools, passing checks, JUnit XML results, Cobertura XML coverage against the plan's minimum, every test passing, every unit tested (TOOL_VERSION_MISMATCH, COMMAND_FAILED, MISSING_RESULTS, MISSING_COVERAGE, COVERAGE_BELOW_MINIMUM, FAILED_TEST, UNTESTED_UNIT). `agent/stages.yaml` loads them at stages 5 and 6; their gates are still planned. Origin: internal.
- **The methods of stages 5 and 6.** `plugins/swe/derive_unit_tests_plugin` (the tester: never reads the code; per component the test list from the acceptance criteria and the input ranges, one stub per unit, the tests, a red run, one test-only commit) and `plugins/swe/derive_unit_code_plugin` (the coder: replaces each stub in place until its tests pass, refactors, runs the stack's checks and suites, never edits a test; a unit that does not fit the design goes back to stage 4). Both follow the method standard; the coder takes from Gentle-AI's `sdd-apply` only the smallest test command that proves a unit. Origin: internal.
- **The gates of stages 5 and 6, built.** `check_verification_plan_gate`, `verify_test_first_gate` (a stub and a test per unit; over the pull request's commits, base..HEAD, test-only commits that change no code, no unit's code before its test, and a red run of each test-only commit in its own worktree where every new or changed test fails or errors), `verify_code_to_design_link_gate`, `check_stack_commands_gate` and `verify_tests_to_requirements_link_gate`, on five new tools: `read_commit_range_tool`, `read_unit_markers_tool`, `read_test_results_tool` (JUnit testcase → test file by file attribute or classname path), `read_coverage_tool` (Cobertura) and `run_stack_commands_tool` (each command once per tree, kept under `.qf/runs/`). `stack.v1` gains `code_files` and a `version_command` for every check and suite. Gates take `--base` (or `QF_BASE`); the product CI template checks out the whole history, passes the base and has a step for the product's toolchain. Rule IDs added while building: TEST_NOT_COMMITTED, UNMAPPED_RESULT. Tested on small Python products (pytest, pytest-cov, ruff), now a test dependency. The gates are still planned in `agent/stages.yaml`. Origin: internal.
- **Stages 5 and 6 implemented.** `agent/stages.yaml` runs `check_verification_plan_gate` and `verify_test_first_gate` at stage 5 *unit_tests*, and `verify_test_first_gate` again with `verify_code_to_design_link_gate`, `check_stack_commands_gate` and `verify_tests_to_requirements_link_gate` at stage 6 *unit_construction*; `verify_security_tests_gate` and `check_env_config_gate` stay planned. Neither stage has a checkpoint: no tests means stage 5 is due, failing tests stage 6. A commit's red run is kept under its SHA (`.qf/runs/commit-<sha>/`), so walking both stages runs it once. The example product fills both slots with the framework plugins. Origin: internal.
- **Stages 5 and 6 run end to end.** `tests/scenarios/test_swe4_unit_verification.py` continues on a small Python product from where stage 4 ends: the tester's and the coder's methods load with their rulebooks; red tests and stubs move the product to stage 6 and code that passes them to stage 7; a test green on its stub is fixed by a retry; code that stays wrong reaches the architect after 4 attempts; a coder who loosens a test with the code, or marks a unit with a requirement that does not exist, is caught. `verify_test_first_gate` now judges each test at the last test-only commit that changed it, so a test fixed on a retry is judged as fixed and only those commits are checked out. Origin: internal.
- **Environment configuration (principle #23).** `env_variable.v1` (one ```yaml env_variable block per variable in the new `paths.env_variables_file`: name, description, required, example, valid values), declared with the detailed design; `check_detailed_design_contract_gate` checks their form (DUPLICATE_VARIABLE). `stack.v1` gains `env_read_patterns`. `check_env_config_gate`, now built at stage 6, reads the code with those patterns: UNDECLARED_VARIABLE, UNUSED_VARIABLE, UNKNOWN_VARIABLE, INVALID_READ_PATTERN, and UNTESTED_VARIABLE for a required variable no passing test names with `@env[<NAME>]`. `validate_env_config_skill` is loaded at stages 4, 5 and 6, and the three methods say who declares, tests and reads. The Markdown link check skips inline code spans. Origin: internal.
- **Security tests (principle #16).** `interface.v1` gains `security_templates`, required when `external` is true: templates from the framework's catalog of five (`authentication`, `authorization`, `input-validation`, `stored-data`, `outbound-calls`). `verify_security_tests_gate`, now built at stage 6, requires the component at the product's end of each external interface to have, for each template named, a passing unit test with one of its `@unit` markers and `@security[<template>]` (MISSING_SECURITY_TEST), and every marker to name a catalog template (UNKNOWN_TEMPLATE). `create_security_tests_skill` holds the catalog's checklists and is loaded at stages 3, 5 and 6; the tester writes the security tests first, red on the stubs. The Python test product gains an outside user reaching the web app. Origin: internal.
- **Contracts for component and integration verification (SWE.5).** `qf.v1` gains `paths.integration_tests_dir` and `stack.v1` `integration_test_files`, so the unit gates never read component and integration tests; `verification_plan.v1` gains an optional `integration` section — techniques, criteria, infrastructure, regression and the integration `order` of steps, each with its components, preconditions and selection. Origin: internal.
- **Rules and method for component and integration verification (SWE.5).** `verify_integration_skill` (the plan's integration section, `@component` and `@flow` markers, interfaces crossed by tested flows, every step's selection tested) and `emit_log_events_skill` (every event of an observability requirement emitted with event, requirement and correlation_id, and named by a passing integration test marked with the requirement's `@sdoc`), loaded at stage 7; the logging rules also at stage 6. The assembler's method `derive_integration_tests_plugin` fills `create_integration_tests_plugin`; the coder's method says how it runs again at stage 7. Origin: internal.
- **Gates of component and integration verification (SWE.5).** `verify_tests_to_components_link_gate` (MISSING_COMPONENT_TEST, UNKNOWN_COMPONENT, UNTESTED_STEP), `verify_tests_to_flows_link_gate` (MISSING_FLOW_TEST, UNKNOWN_FLOW, UNTESTED_INTERFACE, FAILED_INTEGRATION_TEST, MISSING_RESULTS) and `verify_log_events_gate` (UNTESTED_EVENT) share `tools/read_integration_tool.py`, which runs the integration suite once per tree. `check_verification_plan_gate` requires the integration section once integration tests exist (MISSING_INTEGRATION_SECTION) and checks its order (UNKNOWN_COMPONENT, UNSCHEDULED_COMPONENT); `verify_test_first_gate` reports an integration test changed with code (TEST_CHANGED_WITH_CODE). `read_unit_markers_tool` reads `@component`, `@flow` and the integration tests folder. Origin: internal.
- **Contracts for quality assurance (SUP.1).** `qf.v1` gains `paths.framework_dir` (the framework, a pinned submodule), `paths.ci_file` and `paths.framework_feedback_file`, the slot `review_pull_request_plugin`, and a required `review` section: the reviewer agent's accounts (`agents`) and the person's sample (`sample_every`, the N of *1 in N*). `stack.v1` gains a required `security_scans` section — a `secrets` and a `dependencies` scanner, each with a pinned version and SARIF results (decisions 5–9 of the quality assurance stage). The example product and the test product fill the review slot with the framework's method. Origin: internal.
- **Rules and method for quality assurance (SUP.1).** `review_code_skill` (every delivery a pull request; a declared reviewer agent, never the author, approves the current head with the checklist — correctness, style, traceability, logging — complete; a person approves every architecture pull request and 1 in N of the others; a finding fixed in the pull request stays in the review, one left unfixed becomes a *non-conformance* issue) and `report_framework_feedback_skill` (every framework weakness a complete entry, never worked around silently; every framework version bump accounted for), loaded at stage 9. The reviewer agent's method `derive_review_plugin` fills `review_pull_request_plugin` and posts its review from its own account. `templates/FRAMEWORK_FEEDBACK.md` is the log a product copies. `agent/stages.yaml` gives stage 9 its slot, its rulebooks and its five planned gates, and lists every gate the practices name as planned at stages 10–13 (`check_nonconformances_gate`, `check_escalations_gate`, `report_quality_trends_gate` and `check_retro_actions_gate` at the release, stage 11). Origin: internal.
- **Gates of quality assurance (SUP.1).** `verify_framework_integrity_gate` (FRAMEWORK_NOT_PINNED, FRAMEWORK_MODIFIED, FRAMEWORK_NOT_RELEASED), `verify_required_checks_gate` (BRANCH_NOT_PROTECTED, CHECK_NOT_REQUIRED, PROTECTION_BYPASSABLE, UNOWNED_PATH), `scan_security_gate` (SCAN_NOT_RUN, SECURITY_FINDING — a security-severity of 7.0 or more, or none at all; TOOL_VERSION_MISMATCH), `check_framework_feedback_gate` (INCOMPLETE_FEEDBACK_ENTRY, UNACCOUNTED_FRAMEWORK_BUMP) and `verify_host_settings_gate` (NO_PULL_REQUEST, MERGED_WITHOUT_PULL_REQUEST, MISSING_AGENT_REVIEW, INCOMPLETE_CHECKLIST, MISSING_PERSON_APPROVAL), under `gates/sup/`. `tools/read_host_tool.py` reads GitHub with the read-only token in `QF_HOST_TOKEN`, or a recorded host from `QF_HOST_FILE`; a host that cannot be read crashes the gate, which fails closed. `tools/post_review_tool.py` posts the reviewer agent's review of the current head with the checklist. The framework test `tests/consistency/test_rulebook.py` checks the rulebook is complete (SUP.1 BP2); it found the two tech-stack gates belonging to no practice, now statements of SWE.2 BP3. Tests never read a real host: the `GITHUB_*` and `QF_HOST_*` variables are cleared. Origin: internal.
- **Quality assurance stage implemented (stage 9).** `agent/stages.yaml` runs the reviewer (`review_pull_request_plugin`) loaded with `review_code_skill` and `report_framework_feedback_skill`, gated by `verify_framework_integrity_gate`, `verify_required_checks_gate`, `scan_security_gate`, `check_framework_feedback_gate` and `verify_host_settings_gate`. Seal 4 is a person's review on the host (`checkpoint_on_host`): `record_checkpoint_tool` refuses to write it, and `resolve_stage_tool` reports the stage as awaiting its checkpoint while the person's approval is the only finding — and `--check` fails while it waits, so a sampled pull request cannot merge before it. The product CI template takes the framework from the product's submodule instead of a repository variable an admin could change without a pull request, runs again when a review is submitted or dismissed, and passes `QF_HOST_TOKEN` to the gates. `agent/run_aspice_agent.md` says how the foreman opens the pull request and hands it to the reviewer. `tests/scenarios/test_sup1_quality_assurance.py` drives the stage on the Python fixture product with a recorded host. Origin: internal.
- **Contracts and rules for configuration management (SUP.8).** `qf.v1` gains `paths.releases_dir`, `config_items` (the product's own configuration items, added to the framework's list) and a required `mirror` (the backup repository's URL). New contract `release.v1`: one `<version>.yaml` per release with `version` (SemVer), `changed` (the configuration items changed since the previous release) and `framework` (the pinned framework release); no plugin versions. `record_baseline_skill` holds the stage's rules: Conventional Commits naming a requirement or issue, branch names, a protected main branch, every configuration item under git, the two tracks apart, and a release proposed as a pull request with a computed version, tagged after its merge and present in the mirror.
  Origin: internal
- **Gates of configuration management (SUP.8).** `check_commit_conventions_gate` (NOT_CONVENTIONAL, MISSING_REQUIREMENT_TOKEN, BAD_BRANCH_NAME; main's check-commit-message, check-commit-range and check-branch-name as one gate), `verify_branch_protection_gate` (FORCE_PUSH_ALLOWED, DELETION_ALLOWED), `check_config_items_gate` (MISSING_CONFIG_ITEM, UNTRACKED_CONFIG_ITEM; an empty folder is missing), `check_track_rule_gate` (MIXED_TRACKS, ARCHITECTURE_OFF_BRANCH) and `verify_architecture_tests_gate` (CODE_IN_ARCHITECTURE_PR), all over the pull request's commits; `verify_baseline_gate` (INCOMPLETE_RELEASE_RECORD, WRONG_VERSION, TAG_NOT_ANNOTATED, TAG_NOT_ON_MAIN, MISSING_CONFIG_ITEM) and `verify_backup_gate` (TAG_NOT_IN_MIRROR; an unreachable mirror fails closed). `tools/write_release_tool.py` writes the release record and lists the records not yet tagged; `templates/github/release.yml` tags the merge commit of an accepted release and checks the baseline and the mirror. `read_host_tool` reads whether the main branch allows force-pushes and deletion, and the framework's release tags by name.
  Origin: internal
- **Configuration management stage implemented (stage 10).** `agent/stages.yaml` runs `check_commit_conventions_gate`, `verify_branch_protection_gate`, `check_config_items_gate`, `check_track_rule_gate`, `verify_architecture_tests_gate` (both moved from stage 3's planned gates), `verify_baseline_gate` and `verify_backup_gate`; the stage has no plugin, and `load_skills_tool` returns `plugin: null` for it with `record_baseline_skill`. `run_aspice_agent.md` says how the agent proposes a release and never tags one. `tests/scenarios/test_sup8_configuration_management.py` covers a delivery by convention, a commit off it, and a release proposed, tagged by the release workflow's own step and mirrored. The quality assurance scenario's commits follow the convention now.
  Origin: internal
- **Contracts, rules and method for validation (VAL.1).** `qf.v1` gains `paths.validation_scenarios_dir` (the scenarios: a file naming a wish with `@wish[W-<n>]`), `paths.validation_records_dir` (one record per release, evidence of a baseline and not a configuration item) and the slot `create_validation_scenarios_plugin`. New contract `validation.v1`: per release, the environment, the deployed commit and every scenario's technique and result. `verification_plan.v1` gains an optional `validation` section — per scenario in run order its technique, pass/fail criteria, entry criteria and environment, plus the selection and the regression rule. `stack.v1` gains the `validation` suite (no requirement names it) and an optional `validation_test_files`. New rulebook `validate_release_skill` (R1–R11; R11 is checkpoint 5) and the built-in method `derive_validation_scenarios_plugin`, which writes the scenarios from the wishes, the diagrams and the outside interfaces only, never the requirements or the code.
  Origin: internal
- **Gates of validation (VAL.1).** `verify_acceptance_to_wishes_link_gate` (on every pull request MISSING_SCENARIO and UNKNOWN_WISH; while a release is proposed UNVALIDATED_WISH — a release that changes what the customer gets affects every wish) and `verify_release_evidence_gate` (MISSING_VALIDATION_RECORD, also for every release tag; WRONG_DEPLOYED_COMMIT — after the deployed commit only the validation record and the customer's decision may change; UNKNOWN_SCENARIO, MISSING_RESULT for an automated scenario, FAILED_SCENARIO; MISSING_CUSTOMER_DECISION and RELEASE_REJECTED, so seal 5 blocks the merge). `check_verification_plan_gate` requires the validation section once a scenario exists (MISSING_VALIDATION_SECTION, UNSELECTED_SCENARIO, UNKNOWN_SCENARIO). New `tools/write_validation_record_tool.py`: runs the `validation` suite after the deployment and writes the record, keeping the results entered by hand for the same deployment. The scenarios folder is a configuration item, required by `check_config_items_gate` once it exists; the validation records and the customer's decision on a release are no changed items of the release record. Checkpoint 5 is due only while a release is proposed and covers its release record and validation record; the resolver shows it as awaited while the customer's decision is the only finding, and never counts a stage that is not built as done, whether or not its checkpoint is due. The verification report never runs the `validation` suite and, while a release is proposed, adds per wish its scenarios, their results and the customer's decision.
  Origin: internal
- **Validation stage implemented (stage 11).** `agent/stages.yaml` runs the village crew (`create_validation_scenarios_plugin`) loaded with `validate_release_skill`, gated by `verify_acceptance_to_wishes_link_gate` and `verify_release_evidence_gate`, closing with checkpoint 5 while a release is proposed; `check_nonconformances_gate`, `check_escalations_gate`, `report_quality_trends_gate` and `check_retro_actions_gate` stay planned and are reported as not run. `agent/run_aspice_agent.md` says how a delivery gets its scenarios and how a release is deployed by the product's pipeline, recorded and put to the customer. New scenario `tests/scenarios/test_val1_validation.py`: a wish without a scenario, a release validated and waiting for the customer with CI red, accepted, tagged with its record, rejected, and changed after its deployment.
  Origin: internal
- **Contracts and rules for problem resolution (SUP.9) and the faults left open (SUP.1 BP5–BP7).** New contracts `problem.v1` (what, where, how to reproduce, expected, actual, status; then cause, impact by identifier, severity, affected parties, notification date, change request), `nonconformance.v1` (`found_in`, `fixed_by`) and `retro_action.v1` (`owner`, `due`), each a fenced YAML block in the body of a host issue labelled *problem*, *non-conformance* or *retro-action*. `qf.v1` gains the required `urgent_approvers` and `escalate_after_days`. New rulebooks `resolve_problems_skill` (stage 12: R1–R10, the commands `/authorize-urgent-fix` and `/confirm-fixed`, the marker `@problem[<n>]`) and `track_nonconformances_skill` (loaded at stage 9 with the reviewer: R1–R5).
  Origin: internal
- **Gates of problem resolution (SUP.9) and of the faults left open (SUP.1 BP5–BP7).** `check_problem_record_gate` (INCOMPLETE_PROBLEM_RECORD, MISSING_ANALYSIS — on every pull request for every problem a test names, so before its fix merges; MISSING_ALERT at release), `check_urgent_fix_gate` (UNAUTHORIZED_URGENT_FIX: a critical fix needs `/authorize-urgent-fix` from a person in `urgent_approvers` before it reaches the main branch), `verify_problem_closure_gate` (UNKNOWN_PROBLEM; at release MISSING_PROBLEM_TEST, CLOSED_WITHOUT_FIX unless a change request carries the fix, MISSING_CONFIRMATION — `/confirm-fixed` from the reporter after the fix), `report_problem_trends_gate` and `report_quality_trends_gate` (MISSING_TREND_SECTION), `check_nonconformances_gate` (NONCONFORMANCE_WITHOUT_FIX), `check_escalations_gate` (UNESCALATED_NONCONFORMANCE) and `check_retro_actions_gate` (OVERDUE_RETRO_ACTION). `tools/read_host_tool.py` reads issues and their comments, and an issue's fenced block checked against its contract; `tools/read_unit_markers_tool.py` finds `@problem[<n>]` in the tests of every level; `tools/read_commit_range_tool.py` tells when a text first reached the main branch. While a release is proposed, the verification report counts the problems and the non-conformances since the previous release.
  Origin: internal
- **Problem resolution stage implemented (stage 12), and the SUP.1 release gates built.** `agent/stages.yaml` runs the tester (`create_unit_tests_plugin`) and then the coder at stage 12, loaded with `resolve_problems_skill` and `enforce_test_first_skill`; stage 11 runs the four SUP.1 release gates, no longer planned. Once every flow stage is done, the resolver runs the gates of every built event stage, so the repair rules hold on every pull request; `run_gates_tool.py --all` includes them. `agent/run_aspice_agent.md` says how a crack is recorded, analysed, authorized, reproduced first, fixed and confirmed. New scenario `tests/scenarios/test_sup9_problem_resolution.py`.
  Origin: internal
- **Contract and rules for change request management (SUP.10).** New contract `change_request.v1` (what, initiator, reason, status; then the affected wishes, diagram elements and requirements, dependencies, size, and the problem that caused it), a fenced YAML block in the body of a host issue labelled *change-request*. `qf.v1` gains the required `change_approvers`. New rulebook `manage_changes_skill` (stage 13: R1–R10, the commands `/approve-change` and `/confirm-change`; commits name the change they build, `#<n>`).
  Origin: internal
- **Gates of change request management (SUP.10), and the stage implemented (stage 13).** `check_change_record_gate` (INCOMPLETE_CHANGE_RECORD, MISSING_CHANGE_ANALYSIS, UNKNOWN_DEPENDENCY — on every pull request for every change request its commits name, at release for all), `verify_change_approval_gate` (UNAPPROVED_CHANGE: `/approve-change` from a person in `change_approvers` before the first commit naming the change), `verify_change_trace_gate` (UNKNOWN_AFFECTED_ITEM, UNLINKED_PROBLEM) and `verify_change_closure_gate` (at release CLOSED_WITHOUT_IMPLEMENTATION, MISSING_CHANGE_CONFIRMATION — `/confirm-change` from the initiator after the last commit — and MISSING_CHANGE_SECTION). `tools/read_commit_range_tool.py` reads the issue numbers commit messages name; while a release is proposed, the verification report lists the change requests it implements and those still open. `agent/stages.yaml` runs stage 13 with `manage_changes_skill` and no plugin; every stage of the V is now built. New scenario `tests/scenarios/test_sup10_change_request.py`.
  Origin: internal
- **Contracts for software verification (SWE.6).** `qf.v1` gains `paths.software_tests_dir` and `paths.observability_dir`, `stack.v1` gains `software_test_files` and a per-suite `measurements` path, and `verification_plan.v1` an optional `software` section — techniques, criteria, environment, selection, regression and the order of suites. The new `measurements.v1` holds the values a suite measured for non-functional requirements: requirement, value and unit (decision 6 of the software verification stage). Origin: internal.
- **Rules and method for software verification (SWE.6).** `verify_software_skill` (the plan's software section; a passing `@sdoc` test per requirement — system-level ones in the `e2e` suite, software-level ones in the `software` suite, constraints proved by the materials seal; a measured value per non-functional requirement meeting its threshold; the verification report) and `configure_observability_skill` (every observability requirement watched by a definition under `paths.observability_dir` naming it), loaded at stage 8 with `specify_nfr_measurement_skill`. The bridge tester's method `derive_software_tests_plugin` fills `create_software_tests_plugin`; the coder's method says how it runs again at stage 8. Origin: internal.
- **Gates of software verification (SWE.6).** `verify_software_tests_to_requirements_link_gate` (UNVERIFIED_REQUIREMENT — system-level requirements in the `e2e` suite, software-level ones in the `software` suite; UNKNOWN_REQUIREMENT, FAILED_TEST, MISSING_RESULTS), `verify_nfr_thresholds_gate` (MISSING_MEASUREMENT, THRESHOLD_NOT_MET, SCHEMA_VIOLATION on a broken measurements file), `check_observability_gate` (UNOBSERVED_REQUIREMENT, UNKNOWN_REQUIREMENT) and `check_verification_report_gate` (MISSING_REPORT, STALE_REPORT). `tools/write_verification_report_tool.py` runs every declared suite once per tree and writes `report.md` and `report.json` under `.qf/runs/<tree-hash>/` — per unit-test file, per component, flow and integration step, and per requirement what proves it and its latest result. `tools/read_software_tool.py` holds what proves a requirement, the threshold comparison and the measurements reader; `run_stack_commands_tool` keeps each suite's measurements with its run; `read_integration_tool` runs any suite (`run_suite`) and reads the plan's integration steps. `check_verification_plan_gate` requires the software section once software-level tests exist (MISSING_SOFTWARE_SECTION); `verify_test_first_gate` reports a software-level test changed with code or not committed. Origin: internal.
- **Software verification stage implemented (stage 8).** `agent/stages.yaml` runs the bridge tester (`create_software_tests_plugin`) and then the coder (`also_slots: create_unit_code_plugin`), loaded with `verify_software_skill`, `configure_observability_skill` and `specify_nfr_measurement_skill`, and gated by `check_verification_plan_gate`, `verify_test_first_gate`, `verify_software_tests_to_requirements_link_gate`, `verify_nfr_thresholds_gate`, `check_observability_gate` and `check_verification_report_gate`. The product CI template writes the verification report before the gates, shows it as the run summary and keeps it as an artifact. The example product's software tests slot is the framework method. `tests/scenarios/test_swe6_software_verification.py` drives the stage on the Python fixture product, whose measured requirements use a `bench` suite. Origin: internal.
- **Stage 7 implemented.** `agent/stages.yaml` runs `check_verification_plan_gate`, `verify_test_first_gate`, `verify_tests_to_components_link_gate`, `verify_tests_to_flows_link_gate` and `verify_log_events_gate` at stage 7 *integration_verification*, with the assembler's slot and the coder's in turn (`also_slots`); the example product and the Python test product fill it with `derive_integration_tests_plugin`. A scenario walks the stage from the end of stage 6 to stage 8. Origin: internal.
- **Testability declared in the architecture (principle #15).** `interface.v1` gains `implementations` — the `real` implementation of its `to` end and a `double` (stub, fake, in-memory or mock, with a name); `component.v1` gains `composition_root`, absent for an external. Both are optional in the schema and required by `check_testability_gate`. The examples, the test product and the scripted architecture outputs declare them. Origin: internal.
- **`ensure_testability_skill`.** The rules of a testable architecture at stage 3: a composition root per component, a real implementation and a test double per interface, external ones included — each naming its `check_testability_gate` rule ID — and the reviewer's check that units do not create concrete implementations outside the composition root. Origin: internal.
- **`check_testability_gate`, no longer planned.** Runs at stage 3 after checkpoint 3: MISSING_COMPOSITION_ROOT, MISSING_IMPLEMENTATIONS, and NO_ARCHITECTURE on an empty architecture (it fails closed, like check_design_contract_gate). A block that breaks its contract is left to check_design_contract_gate. `agent/stages.yaml` loads `ensure_testability_skill` at stage 3 and lists `verify_architecture_tests_gate` as planned; `derive_architecture_plugin` asks for the composition roots and the test doubles. Origin: internal.

### Changed

- **The documentation states what is.** *docs/Quality_framework_documentation.md* describes the framework in the present tense: no dates, no "decided", no comparison with the earlier framework in §§ 1–5. Each stage's rules are under § 5 *How each stage works*, numbered as the code cites them. Appendix A records the forks — the options weighed, the one chosen and why the others were not — so a later revision does not repeat them and changes an answer on purpose; Appendix B keeps where the practices came from. Stale statements found on the way were corrected: five checkpoints, the slot table with the shipped methods, *tools/* for shared code, the stage table's gates for stages 3 and 10.
- **The diagrams show the flow as it is.** The flowchart and both sequence diagrams name, per stage, every plugin, framework skill and gate of *agent/stages.yaml*; stages 12 and 13 start on their own event; a rejected release closes its pull request and comes back as a wish; the person deploys to staging and CI tags the release; the agent's inside is drawn with its real tools. `tests/consistency/test_diagrams.py` fails when a diagram drifts from the manifest. Corrected on the way: `check_track_rule_gate` (stage 10) and `check_nonconformances_gate` (stage 11) were drawn at stages 3 and 9, and a rejection was drawn as a route into problem resolution. Origin: internal.
  Origin: internal

### Fixed

- **SWE.2 BP2 claimed checks nothing ran (C3).** The final version said `check_design_contract_gate` checks the behaviour diagrams and the modes and concurrency; the architecture stage had left them ungated. New rules: UNKNOWN_PARTICIPANT (every participant of a sequence diagram is a node of an architecture diagram) and UNKNOWN_MODE (a mode moves only to modes of its component). `component.v1` requires `modes` (each with the modes it moves to) and `concurrency` for a component, either as `not_applicable` with the reason, and neither for an external. The example's login diagram names `web-app` and `auth-service` instead of `user` and `auth`, with its checkpoint-1 approval re-recorded; requirements, wish links and scripted outputs follow.
  Origin: found writing the detailed design stage's contract
- **SWE.2's final version claimed three checks nothing ran (C2).** `check_design_contract_gate` was said to verify an embedded, unchanged diagram, a size per component and an acceptance criterion assigned to every component; it checked none. *Embedded unchanged* is replaced by the `derived_from` links the gate already checks (also in SWE.2 BP2 and SWE.3 BP1/BP2); `component.v1` gains a required `size` (S, M, L, XL; absent for an external); acceptance criteria are assigned at the requirement's grain, through `meets`, which UNMET_REQUIREMENT already checks. `write_design_skill`, `derive_architecture_plugin`, the examples and the scripted plugin outputs carry the size. `contracts/README.md` listed 9 of the 15 contracts; it now lists all, and `tests/schema/test_contracts.py` keeps the table and the contract files equal in both directions.
  Origin: found writing the detailed design stage's contract
