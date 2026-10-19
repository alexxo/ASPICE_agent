---
name: verify_integration_skill
description: "Rules for component and integration verification (SWE.5): the integration section of the verification plan with its order of steps; a component test per component marked @component, an integration test per approved sequence diagram marked @flow, every interface between components crossed by a tested flow, every step's selection tested, every test passing; tests in their own folder, never changed with code."
---

# skill: verify_integration_skill

**Stage:** 7 · SWE.5 Software component verification and integration verification
**Loaded with:** create_integration_tests_plugin, create_unit_code_plugin
**Contract:** contracts/verification_plan_contract.v1.schema.json
**Gates:** check_verification_plan_gate, verify_test_first_gate, verify_tests_to_components_link_gate, verify_tests_to_flows_link_gate, check_time_budget_gate

## What it governs

The tests of the big pieces: each component on its own, through its own
interfaces with test doubles on the other side (component tests), and the
components joined along the approved sequence diagrams (integration tests).
They live in *qf.yaml paths.integration_tests_dir*, in files matching the
integration suite's *test_files*, and run in the plan's *integration* suite.
The assembler writes them and the plan's integration section; the coder then
changes the code until they pass and never touches a test.

## Inputs

- The **architecture** — the components, their interfaces and test doubles.
- The **approved sequence diagrams** (*diagrams_dir*) — the flows.
- The **requirements** each component meets and the flows' invariants.
- The **verification plan** — its unit section, to extend.
- The **tech stack** — its *test_runner* rows, the tools a suite can run with.
- On a retry: the **findings** of the previous attempt.

## Contract

The *integration* section of the ```yaml verification_plan block
(*verification_plan.v1*): techniques, pass/fail criteria, entry and exit
criteria, infrastructure, regression, an optional *time_budget* (default 300 s) and the *order* — the steps in which the
components are integrated, each with its *components*, its *preconditions*
and its *selection*: the flows and components whose tests run after it. Its
*suites* hold the *integration* suite: its *tool* (a *test_runner* of the
stack), *run*, *results* and *test_files*, relative to
*paths.integration_tests_dir*.

A component test names its component as *@component[&lt;component-id&gt;]*; an
integration test names its flow as *@flow[&lt;sequence-diagram-id&gt;]*.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Once integration tests exist, the plan has its integration section; the order names existing components and every component of role component | check_verification_plan_gate · MISSING_INTEGRATION_SECTION, UNKNOWN_COMPONENT, UNSCHEDULED_COMPONENT |
| R2 | Every component of role component has a passing component test, and every @component names one | verify_tests_to_components_link_gate · MISSING_COMPONENT_TEST, UNKNOWN_COMPONENT |
| R3 | Every step of the order has a passing test among its selection | verify_tests_to_components_link_gate · UNTESTED_STEP |
| R4 | Every approved sequence diagram has a passing integration test, and every @flow names one | verify_tests_to_flows_link_gate · MISSING_FLOW_TEST, UNKNOWN_FLOW |
| R5 | Every interface between two components is crossed by a message of a tested flow | verify_tests_to_flows_link_gate · UNTESTED_INTERFACE |
| R6 | The integration suite writes its results, and every component and integration test passes | verify_tests_to_flows_link_gate · MISSING_RESULTS, FAILED_INTEGRATION_TEST |
| R7 | No component or integration test changes in a commit that changes code | verify_test_first_gate · TEST_CHANGED_WITH_CODE |
| R8 | Component tests are black-box, through the component's interfaces only, and the selection and order make sense | Checkpoint 4 |
| R9 | An integration test tests each interaction once, never a rule a unit test already shows | check_time_budget_gate · SUITE_OVER_BUDGET |

## Not checkable

The reviewer agent at the pull request, and a person on the sampled pull
requests (checkpoint 4), confirm:

- A component test reaches the component only through its interfaces, with
  the declared test doubles on the other side.
- An integration test follows its flow's messages, not just its first one.
- The order, its preconditions and the selections fit the architecture.

## Example

```yaml verification_plan
contract: verification_plan.v1
unit:
  techniques: [one test per acceptance criterion]
  pass_fail_criteria: every selected unit test passes
  entry_criteria: [the detailed design is merged]
  exit_criteria: [every unit test passes]
  infrastructure: [JUnit 5]
  selection: every unit test on every pull request
  regression: all unit tests run again
  coverage: {metric: lines, minimum: 80}
  suites:
    unit:
      tool: maven
      run: mvn -q test
      results: target/surefire-reports/TEST-*.xml
      coverage: target/site/cobertura/coverage.xml
      test_files: ["**/*Test.java"]
integration:
  techniques:
    - one component test per component, through its own interfaces
    - one integration test per approved sequence diagram
  pass_fail_criteria: every component and integration test passes; a failing test blocks the merge
  entry_criteria: [every unit test passes]
  exit_criteria: [every component, flow and step has a passing test]
  infrastructure: [PostgreSQL 16 in a container]
  regression: every test of a changed component and of its neighbours
  order:
    - step: the auth service alone
      components: [auth-service]
      preconditions: [database migrated]
      selection: [auth-service]
    - step: the web app joins
      components: [web-app]
      preconditions: [auth service healthy]
      selection: [web-app, login]
  suites:
    integration:
      tool: maven
      run: mvn -q verify -Pintegration
      results: target/failsafe-reports/TEST-*.xml
      test_files: ["**/*IT.java"]
```
