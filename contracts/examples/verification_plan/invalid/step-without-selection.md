# Invalid example

```yaml verification_plan
contract: verification_plan.v1
unit:
  techniques:
    - one test per acceptance criterion of the requirements the component meets
    - boundary values at every range limit (min, max, just outside)
  pass_fail_criteria: every selected unit test passes; a failing test blocks the merge
  entry_criteria:
    - the detailed design of the component is merged
  exit_criteria:
    - every unit test passes
    - line coverage reaches the minimum below
  infrastructure:
    - JUnit 5 test runner
    - Mockito for test doubles
  selection: every unit test on every pull request
  regression: all unit tests run again on every change
  coverage: {metric: lines, minimum: 80}
integration:
  techniques:
    - one component test per component, through its own interfaces
    - one integration test per flow of the approved sequence diagrams
  pass_fail_criteria: every component and integration test passes; a failing test blocks the merge
  entry_criteria:
    - every unit test passes
  exit_criteria:
    - every component, flow and integration step has a passing test
  infrastructure:
    - PostgreSQL 16 in a container
    - a stub for the e-mail service
  regression: every test of a changed component and of its neighbours runs again
  order:
    - step: storage first
      components: [auth-service]
      preconditions: [database migrated]
    - step: the web app joins
      components: [web-app]
      preconditions: [auth service healthy]
      selection: [web-app, login]
```
