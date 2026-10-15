---
name: run_verification_suites_skill
description: "Rules for running the product's verification in SWE.3 BP3 and SWE.4: the workshop standards and the unit suite run with the commands and pinned tools the stack declares, every suite writes JUnit XML results, the unit suite writes Cobertura XML coverage, every test passes, every unit has a passing test, and coverage reaches the plan's minimum."
---

# skill: run_verification_suites_skill

**Stage:** 6 · SWE.3 unit construction (BP3) + SWE.4 Software unit verification (BP2–BP5)
**Loaded with:** create_unit_code_plugin
**Contract:** contracts/stack_contract.v1.schema.json
**Gates:** check_stack_commands_gate, verify_tests_to_requirements_link_gate

## What it governs

How the product's own verification runs. The framework knows no language: it
runs only the commands the stack declares, and reads their results in two fixed
formats — JUnit XML for test results, Cobertura XML for coverage. The coder runs
them while working; the gates run them again on every CI run.

## Inputs

- The **tech stack** in *qf.yaml paths.stack_file* — the *checks* (lint,
  format, static analysis), the *suites* with their *run*, *tool*, *version*,
  *results* and *coverage*, and *test_files*.
- The **verification plan** — the unit section's selection, regression,
  *on_change* and minimum coverage.
- The **detailed design** — the units every passing test must cover.
- On a retry: the **findings** of the previous attempt.

## Contract

*stack.v1* declares, for every check and suite, the command, its tool and the
tool's exact version. Every suite writes its results as JUnit XML to *results*
(a path, or a glob for tools that write one file per test class); the unit suite
also writes its coverage as Cobertura XML to *coverage*. A tool that writes
another format is configured to write these, or converted by a step of the
command itself.

The gates tie every JUnit *testcase* to its test file: by its *file*
attribute, or else by its *classname* read as a path. Maven Surefire and
pytest (default *xunit2*) need nothing more. Other runners are configured to
write one of the two — e.g. *jest-junit* with *addFileAttribute: true*. A
result that matches no test file is a finding.

On a change, a suite whose stack entry declares *run_selected* and whose plan
section says *on_change: selected* runs only the tests traced to the change:
*select_tests_tool* follows the changed files' *@unit*, *@component*, *@flow*
and *@sdoc* markers, fills *{tests}* with the selected test files (*paths*) or
their names (*names*), and every selected test keeps its reason for the
verification report. A change that traces to nothing, *QF_RUN=full* and a
proposed release run every test. While working, the coder runs the same
selection: `python .framework/tools/select_tests_tool.py --root .` lists it.

Each command runs once per state of the working tree; the framework keeps what
it produced under *.qf/runs/*. Git must ignore *.qf/* and every path a command
writes — results, coverage, build output — or each run changes the tree and
the next gate runs the command again.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every declared check and suite runs with the tool version the stack pins | check_stack_commands_gate · TOOL_VERSION_MISMATCH |
| R2 | Every check passes with zero errors, and every suite command completes | check_stack_commands_gate · COMMAND_FAILED |
| R3 | Every suite writes its JUnit XML results where the stack says, and the unit suite its Cobertura XML coverage | check_stack_commands_gate · MISSING_RESULTS, MISSING_COVERAGE |
| R4 | The measured coverage reaches the minimum of the verification plan, in its metric | check_stack_commands_gate · COVERAGE_BELOW_MINIMUM |
| R5 | Every result belongs to a test file, and every test in the results passes | verify_tests_to_requirements_link_gate · UNMAPPED_RESULT, FAILED_TEST |
| R6 | Every unit of the detailed design has at least one passing unit test in the results | verify_tests_to_requirements_link_gate · UNTESTED_UNIT |
| R7 | The coverage minimum is judged on a full run only; a selected run covers part of the code | check_stack_commands_gate · COVERAGE_BELOW_MINIMUM |
| R8 | On a selected run, every unit it covers — the units traced to the change — has a passing unit test; on a full run, every unit | verify_tests_to_requirements_link_gate · UNTESTED_UNIT |
| R9 | The commands run the tests the plan selects, and *run_selected* runs exactly the tests given in *{tests}* | Checkpoint 4 |

## Not checkable

The reviewer agent confirms at the pull request, and a person on the sampled
pull requests (checkpoint 4):

- The commands run the tests the plan selects, and nothing is skipped to make a
  run pass.
- The coverage counts the product's code, not generated or excluded files.

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
    run: >-
      mvn -q test jacoco:report &&
      python3 tools/cover2cover.py target/site/jacoco/jacoco.xml src/main/java
      > target/site/cobertura/coverage.xml
    tool: maven
    version: 3.9.9
    version_command: mvn -v
    results: target/surefire-reports/TEST-*.xml
    coverage: target/site/cobertura/coverage.xml
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
