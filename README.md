# ASPICE Agent

**Goal.** Build software products with AI agents that an ASPICE 4.1 assessment
would accept: every feature starts as a diagram, its requirements are derived
from the diagram, every requirement is tested, and every step leaves the evidence
an auditor needs — without a person writing that evidence by hand.

**How.** The ASPICE Agent walks a product through the V, one stage at a time:
diagram, requirements, architecture, detailed design, unit tests and code,
integration and software verification, review, baseline and release. At each
stage it loads the stage's method and the framework's rules, does the work,
checks the result with deterministic gates, retries on what they find, and calls
a person in at the checkpoints that need one.

**Philosophy.**

- **Principles first.** Sixteen principles — requirements-driven development,
  traceability, test first, security, logging, review, acceptance and more — are
  the source of truth. Every principle becomes a checkable practice, and every
  practice has a gate. Nothing is declared that is not checked.
- **Gates, not opinions.** Whether a stage is done is decided by scripts that no
  agent can influence, never by the agent's own judgement. Agents do the work;
  gates judge it; people decide at the checkpoints.
- **Tool-agnostic.** The framework fixes *what* must be true, not *how* to get
  there: the method of each stage is a plugin, the language a stack the product
  chooses, and all state lives in the product's own repository.
- **The right size.** Every measure answers a risk that was rated and found
  high; the rest is a documented, accepted risk. No paid plan, no host settings
  to maintain, no machinery a team does not need.
- **Improve upstream.** A weakness a product team finds is recorded in its
  framework feedback log and fixed in the framework, never worked around.

**Start a new product:** open your coding agent in an empty folder and tell it
to follow [QUICKSTART.md](QUICKSTART.md).

The design and every decision are in
`docs/ASPICE_agent_documentation.md`.

| Directory | Work package | Holds |
|---|---|---|
| `agent/` | WP1 | The ASPICE Agent: the orchestrator (`run_aspice_agent.md`), the start rulebook (`start_product.md`) and its tools |
| `skills/<group>/` | WP2 | The framework skills — contracts and rules loaded with a plugin |
| `gates/<group>/` | WP3 | The gates, one file each, grouped by process (swe, val, sup, principles) |
| `adapters/` | WP3 | Translate a diagram tool's format into `diagram.v1` |
| `tools/` | WP3 | Deterministic helpers shared by gates and adapters |
| `contracts/` | WP0 | The JSON Schemas and their valid and invalid examples |
| `examples/` | All | Example products to run everything against, and a stand-in method plugin |
| `templates/` | All | Files a product copies, e.g. the CI workflow that runs the gates |
| `docs/` | — | The design document and the changelog |
| `tests/` | All | The framework's self-tests |

Every file is named after the entity it holds — `action_what_kind`, e.g.
`check_glossary_gate.py`, `read_archify_diagram_adapter.py` — so the tree reads as
the framework's vocabulary.

Run the tests, from this directory:

```sh
python3 -m venv tests/.venv
tests/.venv/bin/pip install -r tests/requirements-dev.txt
tests/.venv/bin/python -m pytest tests -q
tests/.venv/bin/ruff check . && tests/.venv/bin/ruff format --check .
```

## Start a product

The quick start above does all of this with your agent. By hand:

The product is the repository's root; the framework lives in it once, as a git
submodule at `.framework` checked out at a release. Clone it there, then run the
construction site setup from it with the values only a person can give (the
framework's runtime needs `PyYAML` and `jsonschema`, see `requirements.txt`):

```sh
git clone --branch v1.3.0 git@github.com:alexxo/ASPICE_agent.git my-product/.framework
cd my-product
python .framework/tools/create_product_tool.py --root . \
  --reviewer-agent qf-reviewer-bot --urgent-approver <login> --change-approver <login> \
  --code-owner @<login>
```

It makes the folder a git repository, adopts the clone as the submodule, writes
`qf.yaml`, the CI workflows, `CODEOWNERS` and the feedback log, and stages the
framework's pin at the release. It
commits nothing and never changes the code host, and nothing needs configuring
there: CI reads the host with its own token. Install the diagram plugin
[Archify](https://github.com/tt-a1i/archify) where your agent finds skills, then
start the agent with `.framework/agent/run_aspice_agent.md` — stage 1 begins
with the customer's wishes.

Or let the agent lead right after the clone: open your agent host in
`my-product` and tell it to follow `.framework/agent/start_product.md`. It asks
you the values, runs the same command, walks you through the host steps,
commits with your approval and goes on into stage 1. The rules are in the
design document, § 5 *Starting a product*.

## Try it

Run the SWE.1 gates and the stage resolver on the example product:

```sh
tests/.venv/bin/python gates/swe/check_requirements_contract_gate.py --root examples/login-product
tests/.venv/bin/python agent/resolve_stage_tool.py --root examples/login-product
```

The example has no requirements yet, so the requirement gates fail closed and
the resolver places it at stage 2. `tests/scenarios/test_swe1_slice.py` runs the
whole stage: a pass, a fix by retry, and an escalation to the architect.

## Continuous integration

Every path in this repository is relative to its root.
`.github/workflows/framework-ci.yml` runs the self-test suite
(`python -m pytest tests -q`) and ruff (`ruff check .`, `ruff format --check .`)
on every push and pull request.
