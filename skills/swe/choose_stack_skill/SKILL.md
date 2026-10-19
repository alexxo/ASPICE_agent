---
name: choose_stack_skill
description: "Rules for the tech stack, the first decision of SWE.2: one row per tool the product takes from outside, in its area, every version exact; every area chosen or not needed with a reason; the areas the framework gives as it gives them; a decision record behind it, and the architect's approval at checkpoint 3 before components are designed."
---

# skill: choose_stack_skill

**Stage:** 3 · SWE.2 Software architecture
**Loaded with:** create_architecture_plugin
**Contract:** contracts/stack_contract.v2.schema.json
**Gates:** check_stack_decision_gate, verify_stack_approval_gate

## What it governs

The product's tech stack, in *qf.yaml paths.stack_file*: the first decision of
the architecture, taken after the requirements are approved and before any
component is designed. It lists every tool the product takes from outside, and
only those; how the product is tested — the suite commands — is the
verification plan's. Every plugin generates code for it.

## Inputs

- The **approved requirements** — above all the constraints (a given runtime,
  database or standard) and the non-functional requirements, and the
  verification suites they name.
- The **wishes** of kind constraint.
- **qf.yaml** — *paths.stack_file*, *paths.decisions_dir*, and the slots of the
  diagram and requirements plugins.

## Contract

One YAML file following *stack.v2*. *areas* holds one row per tool: its *area*,
the *tool*, its exact *version* and, optionally, its *purpose*; an area with
several tools (e.g. libraries) has several rows. An area the product does
without has one row, *not_needed*, with the reason. Every stack holds these
areas, and may add its own:

| Area | What it names |
|---|---|
| *language*, *runtime*, *package_manager* | What the code is written in, runs on and installs with |
| *frameworks*, *libraries*, *data_stores* | What the code builds on and keeps its data in |
| *llm*, *external_services* | Models and outside services the product calls |
| *test_runner* | The tools that run the suites, each with its *version_command* |
| *lint*, *format*, *static_analysis* | The coding-principle checks, each with *run* and *version_command* |
| *secrets_scanner*, *dependencies_scanner* | The scanners every pull request runs, each with *run*, *version_command* and its SARIF *results* |
| *build*, *deployment*, *documentation* | How the product is packaged, delivered and documented |
| *version_control*, *ci_cd*, *task_management* | Given by the framework: GitHub, GitHub Actions, GitHub Issues |
| *requirements_engineering*, *diagram_tool* | Given by the framework: the plugin in *qf.yaml*'s slot |

The areas the framework gives carry no version. Besides *areas*: the patterns
of the code files (*code_files*), the patterns that find where the code reads an
environment variable (*env_read_patterns*) and the path of the decision record
that compares the alternatives. The architect reads the stack as a table:
`python .framework/tools/write_stack_table_tool.py --root .` prints it, one row
per tool — *Area · Tool · Version · Status*, chosen or not needed — for the
checkpoint-3 request and the pull request.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | The stack file exists and follows *stack.v2*, every version exact | check_stack_decision_gate · MISSING_STACK, INVALID_STACK |
| R2 | Its decision record exists | check_stack_decision_gate · MISSING_DECISION_RECORD |
| R3 | Every area has a row: its tools, or not needed with the reason; language, test runner, lint, format and the two scanners always name a tool | check_stack_decision_gate · MISSING_STACK_AREA, MISSING_REASON |
| R4 | Every area the framework gives names the tool the framework uses | check_stack_decision_gate · GIVEN_AREA_MISMATCH |
| R5 | The architect approves the stack at checkpoint 3 before any component is designed, and the approval covers its current content | verify_stack_approval_gate · MISSING_APPROVAL, APPROVAL_OUTDATED, APPROVED_TOO_LATE, NOT_A_GIT_REPOSITORY |
| R6 | The stack respects every constraint requirement and fits the non-functional requirements; its test runners can run every suite a requirement names | Checkpoint 3 |

## Not checkable

The architect confirms at checkpoint 3 that the stack respects the constraints,
fits the thresholds of the non-functional requirements, that its test runners
can run every suite the requirements name, that a *not needed* reason holds,
and that the decision record weighed real alternatives.

## Example

```yaml stack
contract: stack.v2
areas:
  - {area: language, tool: java, version: "21"}
  - {area: runtime, tool: temurin, version: 21.0.4}
  - {area: package_manager, tool: maven, version: 3.9.9}
  - {area: frameworks, tool: spring-boot, version: 3.3.4, purpose: HTTP API and security}
  - {area: libraries, not_needed: spring-boot brings every library the service uses}
  - {area: data_stores, tool: postgresql, version: "16.4", purpose: accounts and lockouts}
  - {area: llm, not_needed: the product generates no text}
  - {area: external_services, not_needed: the product calls no outside service}
  - {area: test_runner, tool: maven, version: 3.9.9, version_command: mvn -v}
  - {area: lint, tool: checkstyle, version: 10.18.2, version_command: mvn -q checkstyle:help,
     run: mvn -q checkstyle:check}
  - {area: format, tool: spotless, version: 2.43.0, version_command: mvn -q spotless:help,
     run: mvn -q spotless:check}
  - {area: static_analysis, not_needed: checkstyle covers the rules the team keeps}
  - {area: secrets_scanner, tool: gitleaks, version: 8.21.2, version_command: gitleaks version,
     run: gitleaks detect --no-banner --report-format sarif --report-path build/secrets.sarif,
     results: build/secrets.sarif}
  - {area: dependencies_scanner, tool: osv-scanner, version: 1.9.1, version_command: osv-scanner --version,
     run: osv-scanner --format sarif --output build/dependencies.sarif -r .,
     results: build/dependencies.sarif}
  - {area: build, tool: maven, version: 3.9.9, purpose: one jar per release}
  - {area: deployment, tool: docker, version: 27.3.1, purpose: one image per release}
  - {area: version_control, tool: GitHub}
  - {area: ci_cd, tool: GitHub Actions}
  - {area: task_management, tool: GitHub Issues}
  - {area: requirements_engineering, tool: quality-framework/derive_requirements_plugin}
  - {area: documentation, not_needed: the repository's Markdown is the documentation}
  - {area: diagram_tool, tool: archify}
code_files: ["**/*.java"]
env_read_patterns: ['System\.getenv\("([A-Z0-9_]+)"\)']
decision_record: docs/decisions/0001-java-for-the-auth-service.md
```
