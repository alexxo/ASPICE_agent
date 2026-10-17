# login-product — example product

A small product at the start of SWE.1: the wishes are written, the diagrams are
drawn and approved at checkpoint 1, and the glossary exists. The requirements are
not written yet — producing them is the SWE.1 stage the ASPICE Agent runs next,
followed by the architecture (SWE.2): the tech stack, approved at checkpoint 3,
then the components and interfaces. What the plugins would write at each step is
scripted in `tests/scenarios/plugin_outputs/`.

| Path | What it is |
|---|---|
| `qf.yaml` | Framework configuration: paths and slots |
| `docs/wishes.md` | The customer's wishes, W-01 … W-03 |
| `docs/diagrams/` | Archify specs (architecture, sequence), their pictures (stand-ins, to keep the example small) and the invariants file |
| `docs/approvals/` | The checkpoint-1 approval, bound to the SHA-256 of the diagrams and their pictures |
| `docs/glossary.md` | The domain terms |

The plugins are not part of the product: they are tools on the machine of
whoever runs the agent, installed however that person prefers — for this project,
for their user, or system-wide. The agent looks for each skill in the
conventional folders (`.agents/skills`, `.claude/skills`, under the product and
under `~`). If a skill is installed elsewhere, say where in an environment file
that is never committed — `.qf/environment.yaml` for this project, or
`~/.config/quality-framework/environment.yaml` for all of them:

```yaml
skill_dirs:
  - /opt/company/agent-skills
plugins:
  archify: ~/tools/archify/SKILL.md
```

Archify comes from github.com/tt-a1i/archify; the stand-ins are in
`../example-method/skills/`. The requirements, architecture, detailed design,
unit tests, unit construction, integration tests, software tests and review
methods are framework plugins (`quality-framework/derive_requirements_plugin`,
`quality-framework/derive_architecture_plugin`,
`quality-framework/derive_detailed_design_plugin`,
`quality-framework/derive_unit_tests_plugin`,
`quality-framework/derive_unit_code_plugin`,
`quality-framework/derive_integration_tests_plugin`,
`quality-framework/derive_software_tests_plugin`,
`quality-framework/derive_review_plugin`,
`quality-framework/derive_validation_scenarios_plugin`), shipped with the framework, and need no installing; the
detailed design stage also loads Archify, for the design diagrams. CI needs no
plugin at all: it only runs the gates. From the quality assurance stage on, the
gates read GitHub: the framework is the product's submodule at `.framework`, and
CI needs the repository secret `QF_HOST_TOKEN` (see
`templates/github/quality_gates.yml`). A release is a pull request whose record
`tools/write_release_tool.py` writes to `releases/`. It is validated on that
pull request: the product's own pipeline deploys it to staging,
`tools/write_validation_record_tool.py` records the deployed commit and the
results of the scenarios under `validation/scenarios/` in `validation/records/`,
and the customer accepts it (checkpoint 5) before it can merge. After the merge,
`templates/github/release.yml` tags it.
