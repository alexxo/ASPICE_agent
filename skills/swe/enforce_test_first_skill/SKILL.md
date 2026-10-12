---
name: enforce_test_first_skill
description: "Rules for test first in SWE.4: the tester, who never sees the code, commits per component the unit tests and one stub per unit in one test-only commit, every test fails on the last test-only commit that changed it, no unit's code comes before its test, and no test changes together with code."
---

# skill: enforce_test_first_skill

**Stage:** 5 · SWE.4 Software unit verification — unit tests first (BP1); also loaded at stage 6
**Loaded with:** create_unit_tests_plugin, and create_unit_code_plugin at stage 6
**Contract:** contracts/verification_plan_contract.v1.schema.json
**Gates:** verify_test_first_gate, check_verification_plan_gate

## What it governs

Test first, made checkable. At stage 5 the tester writes, for one component at a
time, the unit tests and one stub per unit, without seeing any code; the stubs
only make the tests compile, so every new test fails or errors on them and
none passes (the red run). At stage 6 the coder replaces the stubs and must leave the tests alone.
The tester also writes the unit section of the verification plan, before the
first test.

## Inputs

- The **approved requirements** — the acceptance criteria of the requirements
  each component meets (*meets* in the architecture).
- The **detailed design** in *paths.detailed_design_dir* — the units, their
  inputs and outputs with type, range and unit of measure, and their calls.
- The **interfaces** of the architecture, and their test doubles.
- The **tech stack** — *test_files* and the unit suite's command, *results* and
  *coverage*.
- **qf.yaml** — *paths.code_dir*, *paths.verification_plan_file*.
- **Not** the code: the tester never reads *paths.code_dir* beyond the files it
  writes itself.
- On a retry: the **findings** of the previous attempt.

## Contract

The verification plan: one ```yaml verification_plan block (*verification_plan.v1*)
in *paths.verification_plan_file*, with the unit section — techniques,
pass/fail, entry and exit criteria, infrastructure, selection, regression and
minimum coverage.

The tests and stubs follow the stack, not a schema:

- A **test** is a file matching *test_files* under *paths.code_dir*; it names
  the unit it verifies with *@unit[&lt;unit-id&gt;]*. One test per acceptance
  criterion of the requirements the component meets, and one per range limit of
  every input (*min*, *max*, and just outside, which must be rejected).
- A **stub** is a code file with the unit's signature (its inputs and outputs)
  and a default return (*0*, *false*, empty, *null*) — nothing else — marked
  *@unit[&lt;unit-id&gt;]*. It is generated from the detailed design only.
- Both lie in a folder named after the component, at any depth of
  *paths.code_dir* (a hyphen may be written as an underscore).
- **One test-only commit per component**: its tests, its stubs and, the first
  time, the verification plan — no other code.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | The verification plan exists, holds exactly one block, and the block follows its contract | check_verification_plan_gate · MISSING_VERIFICATION_PLAN, UNREADABLE_BLOCK, MULTIPLE_PLANS, SCHEMA_VIOLATION |
| R2 | Every unit of the detailed design has a stub and at least one test, both marked with its ID | verify_test_first_gate · MISSING_STUB, MISSING_UNIT_TEST |
| R3 | A component's tests and stubs arrive in a test-only commit: no code other than stubs, and no test left uncommitted | verify_test_first_gate · CODE_IN_TEST_COMMIT, TEST_NOT_COMMITTED |
| R4 | At the last test-only commit that added or changed it, the unit suite runs and writes its results, and the test fails or errors — never passes. A test fixed on a retry is judged as fixed; a commit that mixes tests and code is rewritten, not followed by another | verify_test_first_gate · RED_RUN_WITHOUT_RESULTS, TEST_NOT_FAILING |
| R5 | No file of a unit's code is committed before the unit's test | verify_test_first_gate · CODE_BEFORE_TEST |
| R6 | No commit changes a test together with code: the coder leaves the tests alone, and a wrong test goes back to the tester as a finding | verify_test_first_gate · TEST_CHANGED_WITH_CODE |
| R7 | The gate reads the pull request's commits (base..HEAD), so the product is a git repository | verify_test_first_gate · NOT_A_GIT_REPOSITORY |
| R8 | Each test asserts what its acceptance criterion or range limit says, and the techniques of the plan are the ones used | Checkpoint 4 |

## Not checkable

The reviewer agent confirms at the pull request, and a person on the sampled
pull requests (checkpoint 4):

- Each test asserts the right thing: the *Then* of its acceptance criterion,
  or the rejection at a range limit — not merely that something was returned.
- The tester did not read the code.
- The plan's techniques, criteria and infrastructure are the ones really used.

## Example

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
```

A test and its stub, in the component's folder:

```java
// src/test/java/com/acme/auth_service/CountFailuresTest.java
// @unit[count-failures]
@Test void locksAtTheFifthFailure() {
    assertTrue(new CountFailures().locked(5));
}

// src/main/java/com/acme/auth_service/CountFailures.java — the stub
// @unit[count-failures]
class CountFailures { boolean locked(int failedAttempts) { return false; } }
```
