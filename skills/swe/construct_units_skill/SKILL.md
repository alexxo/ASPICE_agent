---
name: construct_units_skill
description: "Rules for the code of SWE.3 BP3: every code file names the unit it implements, every unit of the detailed design is implemented, code lies in its component's folder, requirement markers name requirements that exist, and stubs are replaced in place without touching a test."
---

# skill: construct_units_skill

**Stage:** 6 · SWE.3 unit construction (BP3) + SWE.4 Software unit verification (BP2–BP5)
**Loaded with:** create_unit_code_plugin
**Contract:** contracts/unit_contract.v1.schema.json
**Gates:** verify_code_to_design_link_gate

## What it governs

The code of the units, in *qf.yaml paths.code_dir*: the coder replaces each
stub the tester left with the real unit, until every unit test passes, then
refactors. The code stays consistent with the detailed design in both
directions, and its folders mirror the architecture.

## Inputs

- The **detailed design** in *paths.detailed_design_dir* — the units to build,
  their inputs, outputs and calls.
- The **unit tests and stubs** of stage 5 — the tests are read, never changed.
- The **tech stack** — language, frameworks, libraries, *test_files*.
- The **approved requirements**, for the *@sdoc* markers.
- The **decision records**, for the *@adr* markers of non-obvious choices.
- On a retry: the **findings** of the previous attempt.

## Contract

The units are the ```yaml unit blocks of *unit.v1* in the detailed design; the
code implements them. In every code file under *paths.code_dir* — every file not
matching the stack's *test_files*:

- **@unit[&lt;unit-id&gt;]** names the unit it implements. A unit may span
  several files (helpers, private parts), each with the same marker; a file may
  name several units.
- The file lies in a folder named after the unit's component, at any depth (a
  hyphen in the component ID may be written as an underscore). Everything else
  about the path follows the stack's own conventions.
- **@sdoc[&lt;REQ-UID&gt;]**, where present, names the requirement the code
  implements.

A new unit with its own inputs and outputs is a design change: it goes back to
stage 4, and the tester adds its stub and tests at stage 5.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every code file names at least one unit | verify_code_to_design_link_gate · MISSING_UNIT_MARKER |
| R2 | Every unit marker, in code or tests, names a unit of the detailed design | verify_code_to_design_link_gate · UNKNOWN_UNIT |
| R3 | Every unit of the detailed design is implemented by at least one code file | verify_code_to_design_link_gate · UNIMPLEMENTED_UNIT |
| R4 | Every file with a unit marker lies in a folder named after the unit's component | verify_code_to_design_link_gate · UNIT_OUTSIDE_COMPONENT |
| R5 | Every requirement marker names a requirement that exists | verify_code_to_design_link_gate · UNKNOWN_REQUIREMENT |
| R6 | The code does what the unit's responsibility says, within its ranges, and nothing a unit test did not ask for | Checkpoint 4 |

The coder may not change a test (enforce_test_first_skill R6), and the tests,
workshop standards and coverage must pass (run_verification_suites_skill).

## Not checkable

The reviewer agent confirms at the pull request, and a person on the sampled
pull requests (checkpoint 4):

- The code does what the unit's responsibility says and respects its ranges.
- Helpers stay inside their unit; a unit is not split across components.
- Refactoring kept the code readable and did not add behaviour no test asks for.

## Example

The unit the code implements:

```yaml unit
id: count-failures
derived_from: auth-service#count-failures
name: Count failures
responsibility: Counts consecutive failed sign-ins and locks the account at the limit.
inputs:
  - {name: failed attempts, type: int, range: {min: 0, max: 5}, unit: count}
outputs:
  - {name: locked, type: bool, range: not applicable, unit: not applicable}
calls: [lock-account]
```

The stub of stage 5, replaced in place:

```java
// src/main/java/com/acme/auth_service/CountFailures.java
// @unit[count-failures] @sdoc[REQ-0011]
class CountFailures {
    static final int LIMIT = 5;
    boolean locked(int failedAttempts) { return failedAttempts >= LIMIT; }
}
```
