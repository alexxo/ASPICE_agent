# Quality Framework — next major version

A quality layer over any specification-driven method, organised by the ASPICE
4.1 processes. The framework acts as the **ASPICE Agent**: at each stage it loads
a plugin and the framework's rules, checks the result with deterministic gates,
retries on findings and calls a person in at the checkpoints.

The design and every decision are in
`docs/Quality_framework_documentation.md`.

| Directory | Work package | Holds |
|---|---|---|
| `agent/` | WP1 | The ASPICE Agent: the orchestrator (`run_aspice_agent.md`) and its tools |
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
