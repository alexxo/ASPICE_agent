# Invalid example

How the product is verified, one section per level. The tester writes the unit
section before the first unit test, the assembler the integration section
before the first integration test, the bridge tester the software section
before the first software-level test; all are agreed at the pull request.

## Unit verification

Every unit is tested on its own, through its declared inputs and outputs, with
test doubles for the units and components it calls.

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
  on_change: selected
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
  on_change: selected
  order:
    - step: storage first
      components: [auth-service]
      preconditions: [database migrated]
      selection: [auth-service]
    - step: the web app joins
      components: [web-app]
      preconditions: [auth service healthy]
      selection: [web-app, login]
software:
  techniques:
    - one test per acceptance criterion of every requirement, through the product's outside interfaces
    - one benchmark per performance requirement, against its threshold
  pass_fail_criteria: every software-level test passes and every measured value meets its threshold
  entry_criteria:
    - every component and integration test passes
  exit_criteria:
    - every requirement has a passing software-level test or a measured value
  infrastructure:
    - the product deployed in a test environment with sample data
  selection: every software-level test before every release
  regression: all software-level tests run again before every release
  on_change: selected
  order: [software, bench, e2e]
validation:
  selection: every automated scenario before every release; the market-day demo when a wish about loaded carts changes
  regression: every scenario of a wish the release touches runs again
  scenarios:
    - scenario: validation/scenarios/test_loaded_cart_crosses.py
      technique: acceptance test
      pass_fail_criteria: a 1-tonne cart crosses and the crossing is logged
      entry_criteria: [the release deployed to staging with realistic data]
      environment: staging, with the same integrations as production
    - scenario: validation/scenarios/market-day-demo.md
      technique: guided demo
      entry_criteria: [every automated scenario passed]
      environment: staging, with a market day's load replayed
```
