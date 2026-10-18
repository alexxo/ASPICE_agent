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

Create an empty folder for the product, open your coding agent in it, and tell
it:

> Follow the quick start at
> https://raw.githubusercontent.com/alexxo/ASPICE_agent/main/QUICKSTART.md

The agent walks you through the setup and hands over to the ASPICE Agent
([QUICKSTART.md](QUICKSTART.md)).

## Try it

Run the SWE.1 gates and the stage resolver on the example product:

```sh
tests/.venv/bin/python gates/swe/check_requirements_contract_gate.py --root examples/login-product
tests/.venv/bin/python agent/resolve_stage_tool.py --root examples/login-product
```

The example has no requirements yet, so the requirement gates fail closed and
the resolver places it at stage 2. `tests/journey/test_swe1_slice.py` runs the
whole stage: a pass, and a stuck requirement retried, then escalated to the architect.

## Continuous integration

Every path in this repository is relative to its root.
`.github/workflows/framework-ci.yml` runs the self-test suite in parallel
(`python -m pytest tests -q -n auto --dist loadfile`) and ruff (`ruff check .`,
`ruff format --check .`) on every push and pull request; the full suite fails
over its budget of 420 s. The suite follows
the strategy it asks of products (design document, Appendix A.5, *Fast by
design*), each layer proving one thing once:

| Layer | Folder | Proves |
|---|---|---|
| Static | `tests/consistency`, `tests/schema` | the documents, skills and contracts agree with the code; every rule a gate reports has a unit test |
| Unit | `tests/unit` | each gate's rules, each tool, and the resolver's routing for every stage |
| Seam | `tests/seam` | every gate script runs as a real process and prints one findings.v1 result |
| Journey | `tests/journey` | one happy walk per stage through the real tools and gates |
