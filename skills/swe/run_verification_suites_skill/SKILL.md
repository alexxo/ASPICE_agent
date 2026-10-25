---
name: run_verification_suites_skill
description: "Rules for running the product's verification in SWE.3 BP3 and SWE.4: the workshop standards run with the commands and pinned tools the stack declares, the unit suite with the command the plan declares and the version of its stack test runner, every suite writes JUnit XML results, the unit suite writes Cobertura XML coverage, every test passes, every unit has a passing test, and coverage reaches the plan's minimum."
---

# skill: run_verification_suites_skill

**Stage:** 6 · SWE.3 unit construction (BP3) + SWE.4 Software unit verification (BP2–BP5)
**Loaded with:** create_unit_code_plugin
**Contract:** contracts/verification_plan_contract.v1.schema.json
**Gates:** check_stack_commands_gate, verify_tests_to_requirements_link_gate, check_time_budget_gate

## What it governs

How the product's own verification runs. The framework knows no language: it
runs only the commands the product declares — the checks in the stack, the
suites in the verification plan — and reads their results in two fixed
formats — JUnit XML for test results, Cobertura XML for coverage. The coder runs
them while working; the gates run them again on every CI run.

## Inputs

- The **tech stack** in *qf.yaml paths.stack_file* — the *lint*, *format* and
  *static_analysis* rows with their *run*, *tool*, *version* and
  *version_command*, and the *test_runner* rows.
- The **verification plan** — the unit section's *suites* with their *run*,
  *tool*, *results*, *coverage* and *test_files*, and its selection,
  regression, minimum coverage and *time_budget*.
- The **detailed design** — the units every passing test must cover.
- On a retry: the **findings** of the previous attempt.

## Contract

*stack.v2* declares, for every check, the command, its tool and the tool's
exact version; *verification_plan.v1* declares, for every suite, the command
and the tool, a *test_runner* row of the stack that gives the version. Every suite writes its results as JUnit XML to *results*
(a path, or a glob for tools that write one file per test class); the unit suite
also writes its coverage as Cobertura XML to *coverage*. A tool that writes
another format is configured to write these, or converted by a step of the
command itself.

The gates tie every JUnit *testcase* to its test file: by its *file*
attribute, or else by its *classname* read as a path. Maven Surefire and
pytest (default *xunit2*) need nothing more. Other runners are configured to
write one of the two — e.g. *jest-junit* with *addFileAttribute: true*. A
result that matches no test file is a finding.

CI runs every test of every suite on every change, and each suite runs in
parallel by default. The run keeps how long it took; *check_time_budget_gate*
judges it against the plan's *time_budget*, else the default — the unit suite
120 s and each unit test 0.5 s, the integration suite 300 s, the software suite
600 s. While working, the coder runs the tests traced to the change first: a
suite whose plan entry declares *run_selected* runs them with
*QF_RUN=selected* — *select_tests_tool* follows the changed files' *@unit*,
*@component*, *@flow* and *@sdoc* markers and fills *{tests}* with the
selected test files (*paths*) or their names (*names*), each test with its
reason; `python .framework/tools/select_tests_tool.py --root .` lists them. A
change that traces to nothing and a proposed release select every test.

Each command runs once per state of the working tree; the framework keeps what
it produced under *.qf/runs/*. Git must ignore *.qf/* and every path a command
writes — results, coverage, build output — or each run changes the tree and
the next gate runs the command again.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every declared check and suite runs with the tool version the stack pins — for a suite, its test runner's | check_stack_commands_gate · TOOL_VERSION_MISMATCH |
| R2 | Every check passes with zero errors, and every suite command completes | check_stack_commands_gate · COMMAND_FAILED |
| R3 | Every suite writes its JUnit XML results where the plan says, and the unit suite its Cobertura XML coverage | check_stack_commands_gate · MISSING_RESULTS, MISSING_COVERAGE |
| R4 | The measured coverage reaches the minimum of the verification plan, in its metric | check_stack_commands_gate · COVERAGE_BELOW_MINIMUM |
| R5 | Every result belongs to a test file, and every test in the results passes | verify_tests_to_requirements_link_gate · UNMAPPED_RESULT, FAILED_TEST |
| R6 | Every unit of the detailed design has at least one passing unit test in the results | verify_tests_to_requirements_link_gate · UNTESTED_UNIT |
| R7 | The coverage minimum is judged on a full run only; a selected run covers part of the code | check_stack_commands_gate · COVERAGE_BELOW_MINIMUM |
| R8 | On a selected run, every unit it covers — the units traced to the change — has a passing unit test; on a full run, every unit | verify_tests_to_requirements_link_gate · UNTESTED_UNIT |
| R9 | The commands run the tests the plan selects, and *run_selected* runs exactly the tests given in *{tests}* | Review |
| R10 | Every suite and every unit test runs within its level's time budget — the plan's or the default — and a budget looser than the default states why | check_time_budget_gate · SUITE_OVER_BUDGET, TEST_OVER_BUDGET, MISSING_BUDGET_REASON |
| R11 | Every suite's *run* runs its tests in parallel (e.g. *pytest -n auto*, Maven Surefire's *forkCount*), unless its test runner has no way to | Review |

## Not checkable

The reviewer agent confirms at the pull request, and a person on the
important or risky pull requests (checkpoint 4):

- The commands run the tests the plan selects, and nothing is skipped to make a
  run pass.
- The coverage counts the product's code, not generated or excluded files.

## Example

The unit section's suite; the checks are the stack's *lint* and *format* rows
(see *choose_stack_skill*).

```yaml verification_plan
contract: verification_plan.v1
unit:
  techniques: [one test per acceptance criterion]
  pass_fail_criteria: every selected unit test passes; a failing test blocks the merge
  entry_criteria: [the detailed design of the component is merged]
  exit_criteria: [every unit test passes, line coverage reaches the minimum]
  infrastructure: [JUnit 5 test runner]
  selection: every unit test on every pull request
  regression: all unit tests run again on every change
  coverage: {metric: lines, minimum: 80}
  suites:
    unit:
      tool: maven
      run: >-
        mvn -q test jacoco:report &&
        python3 tools/cover2cover.py target/site/jacoco/jacoco.xml src/main/java
        > target/site/cobertura/coverage.xml
      results: target/surefire-reports/TEST-*.xml
      coverage: target/site/cobertura/coverage.xml
      test_files: ["**/*Test.java"]
```
