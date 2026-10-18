---
name: choose_stack_skill
description: "Rules for the tech stack, the first decision of SWE.2: every version exact, one command per verification suite the requirements name, a decision record behind it, and the architect's approval at checkpoint 3 before components are designed."
---

# skill: choose_stack_skill

**Stage:** 3 · SWE.2 Software architecture
**Loaded with:** create_architecture_plugin
**Contract:** contracts/stack_contract.v1.schema.json
**Gates:** check_stack_decision_gate, verify_stack_approval_gate

## What it governs

The product's tech stack, in *qf.yaml paths.stack_file*: the first decision of
the architecture, taken after the requirements are approved and before any
component is designed. Every plugin generates code for it.

## Inputs

- The **approved requirements** — above all the constraints (a given runtime,
  database or standard) and the non-functional requirements, and the
  verification suites they name.
- The **wishes** of kind constraint.
- **qf.yaml** — *paths.stack_file*, *paths.decisions_dir*.

## Contract

One YAML file following *stack.v1*: language, runtime, frameworks, libraries and
data stores, each with an exact version; the patterns that tell a test file
from code (*test_files*); one command per verification suite (*unit* always),
with where it writes its test results as JUnit XML (*results*) and, for the unit
suite, its code coverage as Cobertura XML (*coverage*), and for the unit,
integration and software suites the command that runs only given tests
(*run_selected*, with *{tests}*, and *selected_form*: *paths* or *names*); the
lint and format
checks; the secrets and dependencies scanners every pull request runs, each
writing its findings as SARIF (*security_scans*); and the path of the decision
record that compares the alternatives.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | The stack file exists and follows *stack.v1*, every version exact | check_stack_decision_gate · MISSING_STACK, INVALID_STACK |
| R2 | Its decision record exists | check_stack_decision_gate · MISSING_DECISION_RECORD |
| R3 | Every verification suite a requirement names has a command in the stack | check_stack_decision_gate · UNKNOWN_INSTRUMENT |
| R4 | The architect approves the stack at checkpoint 3 before any component is designed, and the approval covers its current content | verify_stack_approval_gate · MISSING_APPROVAL, APPROVAL_OUTDATED, APPROVED_TOO_LATE, NOT_A_GIT_REPOSITORY |
| R5 | The stack respects every constraint requirement and fits the non-functional requirements | Checkpoint 3 |
| R6 | Every suite's *run* runs its tests in parallel (e.g. *pytest -n auto*, Maven Surefire's *forkCount*), unless the stack's test runner has no way to | Checkpoint 3 |

## Not checkable

The architect confirms at checkpoint 3 that the stack respects the constraints,
fits the thresholds of the non-functional requirements, and that the decision
record weighed real alternatives.

## Example

```yaml stack
contract: stack.v1
language: {name: java, version: "21"}
frameworks:
  - {name: spring-boot, version: 3.3.4, purpose: HTTP API and security}
code_files: ["**/*.java"]
test_files: ["**/*Test.java"]
integration_test_files: ["**/*IT.java"]
software_test_files: ["**/*ST.java"]
env_read_patterns: ['System\.getenv\("([A-Z0-9_]+)"\)']
suites:
  unit:
    run: mvn -q test
    tool: maven
    version: 3.9.9
    version_command: mvn -v
    results: target/surefire-reports/TEST-*.xml
    coverage: target/site/cobertura/coverage.xml
    run_selected: mvn -q test -Dtest={tests}
    selected_form: names
  integration:
    run: mvn -q verify -Pintegration
    tool: maven
    version: 3.9.9
    version_command: mvn -v
    results: target/failsafe-reports/TEST-*.xml
checks:
  lint:
    run: mvn -q checkstyle:check
    tool: checkstyle
    version: 10.18.2
    version_command: mvn -q checkstyle:help
  format:
    run: mvn -q spotless:check
    tool: spotless
    version: 2.43.0
    version_command: mvn -q spotless:help
security_scans:
  secrets:
    run: gitleaks detect --no-banner --report-format sarif --report-path build/secrets.sarif
    tool: gitleaks
    version: 8.21.2
    version_command: gitleaks version
    results: build/secrets.sarif
  dependencies:
    run: osv-scanner --format sarif --output build/dependencies.sarif -r .
    tool: osv-scanner
    version: 1.9.1
    version_command: osv-scanner --version
    results: build/dependencies.sarif
decision_record: docs/decisions/0001-java-for-the-auth-service.md
```
