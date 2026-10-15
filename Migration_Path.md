# Migration path — from the previous framework to the ASPICE Agent

For a team whose product runs on the previous Quality Framework and has already
started writing requirements from its Archify diagrams. Following these steps
keeps that work: the diagrams stay as they are, and the requirements and
glossary are converted to this framework's contracts instead of being written
again.

The product ends at the start of stage 2 (SWE.1) of this framework, with the
diagrams approved at checkpoint 1 and the requirements converted and approved at
checkpoint 2.

## What you need

- The product repository, with all pending work merged. Do the migration on one
  branch, e.g. `migrate-to-aspice-agent`.
- The person who approves the diagrams and requirements (the architect).
- Python 3.12 or later, and Archify installed where your agent finds skills
  (github.com/tt-a1i/archify).
- The values only a person knows, asked by the setup in step 3: the reviewer
  agent's host account, the urgent approvers, the change approvers, the code
  owners and the mirror URL.

## Why the order matters

The gate `verify_diagram_approval_gate` checks that the diagrams were approved
**before** any requirement was derived. It compares the checkpoint-1 approval date
with the first commit of every `*.md` file under `docs/requirements/`, following
renames (`tools/check_approval_order_tool.py`). Requirement files committed
under the previous framework would make a new approval look late
(`APPROVED_TOO_LATE`).

So:

1. The old requirement files leave `docs/requirements/` before the approval.
2. The converted requirements are written to **new file names**, after the
   approval. A file name that was ever used under `docs/requirements/` keeps its
   old history, even after the file was deleted or moved.

## Step 1 — Take stock

List what the product has today. Every item has a place in the steps below.

| Previous framework | Where it goes |
|---|---|
| `.framework/` submodule (previous framework) | Replaced in step 2 |
| Archify JSON diagrams | `docs/diagrams/`, step 4 |
| `docs/requirements/*.md` (`REQ-<AREA>-<n>`, `DERIVED_FROM`, `ACCEPTANCE_CRITERIA`, `SOURCE`) | `docs/legacy/requirements/` in step 2, converted in step 6 |
| `docs/glossary.md` (`## <TERM>`, `**Definition:**`) | Converted in place in step 6 |
| `tech-stack.yaml`, `tech-stack-integrations/` | `docs/legacy/`; input to stage 3, the tech stack |
| `docs/adr/`, `docs/architecture/`, `docs/design/` | `docs/legacy/`; input to stages 3 and 4 |
| `FRAMEWORK_FEEDBACK.md`, `.github/CODEOWNERS` | `docs/legacy/`; the setup writes new ones, and never overwrites a file |
| Old CI workflow, git hooks, `scripts/local_dry_CI_run_before_commit.sh`, `CHANGELOG(framework).md`, provider version files | Removed: the new CI runs the gates |

## Step 2 — Remove the previous framework

From the product root:

```sh
git switch -c migrate-to-aspice-agent

# The previous framework's submodule: remove it completely, so the setup does not
# keep its URL in .gitmodules.
git submodule deinit -f .framework
git rm -f .framework
rm -rf .git/modules/.framework

# Work kept as input for later stages.
mkdir -p docs/legacy
git mv docs/requirements docs/legacy/requirements
git mv tech-stack.yaml tech-stack-integrations docs/legacy/
git mv docs/adr docs/architecture docs/design docs/legacy/      # those that exist
git mv FRAMEWORK_FEEDBACK.md docs/legacy/
git mv .github/CODEOWNERS docs/legacy/                         # if it exists

# What the new framework replaces.
git rm .github/workflows/quality-gates.yml                     # the old CI workflow
git rm -r scripts/local_dry_CI_run_before_commit.sh            # and the old hooks and version files

git commit -m "chore: remove the previous framework"
```

Leave `docs/glossary.md` where it is: it is converted in step 6.

## Step 3 — Set up this framework

Follow the README's *Start a product*, with the framework at the release tag:

```sh
git clone --branch v1.2.0 git@github.com:alexxo/ASPICE_agent.git .framework
python3 -m venv .qf/venv && .qf/venv/bin/pip install -r .framework/requirements.txt
.qf/venv/bin/python .framework/tools/create_product_tool.py --root . \
    --reviewer-agent LOGIN --urgent-approver LOGIN --change-approver LOGIN \
    --code-owner @LOGIN-OR-@ORG/TEAM --mirror URL
```

The tool writes `qf.yaml`, the CI workflows, `CODEOWNERS`, the framework
feedback log and the `.gitignore` lines, and stages the submodule. If it stops,
it names every file in the way and changes nothing; move that file to
`docs/legacy/` and run it again.

Do the steps it prints on the code host (the `QF_HOST_TOKEN` secret, branch
protection, the mirror). Copy any open entries from
`docs/legacy/FRAMEWORK_FEEDBACK.md` into the new log, then commit:

```sh
git commit -m "chore: set up the ASPICE Agent framework v1.2.0"
```

## Step 4 — Stage 1 inputs: wishes and diagrams

The previous framework had no wishes file and no per-diagram rule files. Add
them next to the existing diagrams.

1. **Wishes** — write `docs/wishes.md`: what the customer asked for, in their
   words, one fenced `yaml wish` block each (`id: W-01`, `statement`, `source`).
   Use `kind: constraint` for a given such as a runtime or a database. See
   `examples/login-product/docs/wishes.md`.
2. **Diagrams** — move each Archify JSON file to `docs/diagrams/` and name it
   `<id>.<type>.json`: the ID in lower-case words joined by hyphens, the type
   its `diagram_type` (`architecture`, `sequence`, `workflow`, `dataflow` or
   `lifecycle`). Keep every element ID unchanged: the requirements refer to
   them.
3. **Every element needs an `id` and a `label`**; every connection and message
   also needs `from` and `to`. Add any ID a diagram was drawn without; the
   gates report each one as `MISSING_ID`.
4. **Invariants** — for each diagram, `<id>.invariants.yaml`: the rules the
   drawing cannot show (`INV-1`, …), each naming the elements it constrains. The
   old requirements often hold these as behavioural rules.
5. **Wish links** — for each diagram, `<id>.wishes.yaml`: which wishes each
   element realises. Every behaviour wish must be realised by some element.

Rules: `skills/swe/draw_diagram_skill/SKILL.md`. Example:
`examples/login-product/docs/diagrams/`.

You can also start the agent (step 5) and let it do this: at stage 1 it grows the
existing diagrams instead of redrawing them.

## Step 5 — Checkpoint 1: approve the diagrams

Start the agent with `.framework/agent/run_aspice_agent.md`. It finds the
product at stage 1, runs the gates and fixes what they find:

```sh
.qf/venv/bin/python .framework/agent/run_gates_tool.py --root . --stage diagram
```

When the gates pass, the architect reviews the diagrams and the agent records
the decision, bound to the SHA-256 of every diagram file:

```sh
.qf/venv/bin/python .framework/agent/record_checkpoint_tool.py --root . \
    --checkpoint 1 --decision approved --approver "NAME" --role architect
git add docs/wishes.md docs/diagrams docs/approvals
git commit -m "feat(diagrams): approve the diagrams at checkpoint 1"
```

From now on, changing a diagram file needs a new approval
(`APPROVAL_OUTDATED`).

## Step 6 — Stage 2: convert the requirements and the glossary

Ask the agent to continue. At stage 2, tell it to use
`docs/legacy/requirements/` as an input: **keep every old requirement's meaning
and acceptance criteria, and write it in the form of
`skills/swe/write_requirements_skill/SKILL.md`**. The method
(`plugins/swe/derive_requirements_plugin/SKILL.md`) then adds what the diagrams
need and the old files lack.

Write one file per feature under `docs/requirements/`, named after the feature's
sequence diagram, and check the name was never used there before:

```sh
git log --all --oneline -- docs/requirements/<name>.md     # must print nothing
```

### Requirement fields

Only the fenced `yaml requirement` blocks count; headings and prose are free.

| Previous framework | This framework |
|---|---|
| `REQ-ARCH-044` | `uid: REQ-0044` — `REQ-` and at least four digits, unique across all files. Keep the old UID in the heading, e.g. `## REQ-0044 · Publisher (was REQ-ARCH-044)` |
| `The system SHALL provide …` | `statement:` — one sentence on one line, observable behaviour, domain terms written `_term_` |
| `DERIVED_FROM: node` with `SOURCE_DIAGRAM_*` | `derived_from: <diagram-id>#<element-id>`, e.g. `wp-foundation#publisher`; a constraint derives from a wish: `W-03` |
| `ACCEPTANCE_CRITERIA` bullets | `acceptance_criteria:` — one item per bullet with `case` (`happy`, `edge` or `error`), `given`, `when`, `then` |
| `RATIONALE` | Prose under the heading |
| — | New: `level` (`system` or `software`), `kind`, `criticality`, `feasibility`, `size`, `environment`, and `refines` for a software requirement |

What the gates also ask, and the old files rarely have:

- every node, edge, message and invariant of an approved diagram is covered by a
  requirement;
- every system requirement is refined by a software requirement;
- every sequence diagram has an `observability` requirement;
- every requirement has a `happy` criterion, and a `high` one also an `edge` or
  `error` criterion;
- non-functional kinds have `metric`, `threshold` and `measurement_method`.

An old requirement no diagram element or wish supports, e.g. *CI runs on GitHub
Actions*, becomes a constraint derived from a new wish, or is dropped when this
framework now covers it.

### Glossary

Rewrite `docs/glossary.md` as fenced `yaml glossary_term` blocks:

| Previous framework | This framework |
|---|---|
| `## <TERM>` | `term:` |
| `**Definition:**` | `definition:` — one sentence |
| `**Examples:**` | `examples:` — a list |
| `**Aliases:**` | `aliases:` — a list |

Every term a requirement uses is written `_term_` in it and defined once here.
Rules: `skills/swe/define_glossary_terms_skill/SKILL.md`.

### Gates and checkpoint 2

```sh
.qf/venv/bin/python .framework/agent/run_gates_tool.py --root . --stage requirements
```

When the gates pass, the architect reviews the requirements against the old ones
and the agent records checkpoint 2 the same way (`--checkpoint 2`). Commit the
requirements, the glossary and the approval.

## Step 7 — Clean up and merge

```sh
git rm -r docs/legacy/requirements
git commit -m "chore: remove the previous framework's requirements"
.qf/venv/bin/python .framework/agent/resolve_stage_tool.py --root .
```

The stage resolver should report stage 3. Push the branch and open its pull
request: the new CI runs the gates. Keep `docs/legacy/` for the stack,
decisions and designs until stages 3 and 4 have used them, then remove it.

## If a gate finds something

Each finding names the rule, the file and the line. Fix it in the files, never in
the framework, and run the gates again. If the framework itself is wrong, write
it in `FRAMEWORK_FEEDBACK.md`
(`skills/sup/report_framework_feedback_skill/SKILL.md`).
