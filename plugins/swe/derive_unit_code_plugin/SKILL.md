---
name: derive_unit_code_plugin
description: "Replaces, component by component, every stub with the real unit from the detailed design until the unit tests written before it pass, then refactors — never editing a test — and runs the stack's checks and suites."
---

# plugin: derive_unit_code_plugin

**Stage:** 6 · SWE.3 unit construction (BP3) + SWE.4 Software unit verification (BP2–BP5)
**Fills slot:** create_unit_code_plugin
**Loaded with:** enforce_test_first_skill, construct_units_skill, run_verification_suites_skill, validate_env_config_skill, create_security_tests_skill, emit_log_events_skill

## Goal

From the detailed design and the failing unit tests to the units themselves:
replace each stub with code that does what the unit's responsibility says,
only as much as the tests ask, until they pass; then refactor. The code stays
consistent with the detailed design and passes the stack's checks.

You are the coder. The tests are fixed: they were written from the requirements
before the code. Changing one to make it pass would hide the very fault it is
there to catch.

Not this method's job: the tests (the previous stage, by the tester), the form
(the rules skills loaded with it), the checks (the stage's gates), the
agreement (the reviewer at the pull request, checkpoint 4 on a sample).

## Explore

Read before writing anything:

- the detailed design of the component — the units, their responsibility,
  inputs and outputs with ranges, and their calls;
- the unit tests and stubs of the component — what must pass, and where each
  unit lives;
- the tech stack — language, frameworks, libraries, the checks and suites;
- the decision records that bear on the component;
- in an existing product, **the code around it: its patterns, helpers and
  conventions**. Follow them unless the change is about them.

## Ask

Ask no person: from stage 4 on the build is the agents' and the gates', and
the person approves the results (checkpoint 4). Settle each question below
yourself, write the choice as an assumption in a comment at the choice and the
commit message, and go on; the reviewer agent judges every assumption:

- a library or existing helper the unit should use rather than reimplement;
- a choice the design leaves open and no test decides — concurrency, error
  handling, performance.

Never resolve a doubt about what a test means by changing it: a test you think
wrong is a finding for the tester.

A question no requirement answers whose answer changes what the user sees or
gets is a question of what is wanted: never ask it in the session. Write it
in the report and the pull request: the reviewer agent sends it to the
person, whose answer changes the requirements (a change request).

## Depth

- **Lite** — a unit whose tests pass with a few lines and no call to another
  unit: build it, run its tests.
- **Full** — calls to other units or components, shared state, or a unit
  meeting a requirement of criticality high: build in small steps, running the
  smallest test command that proves the unit after each, and record a decision
  for every non-obvious choice (*@adr*).

When in doubt, full.

## Steps

One component at a time, unit by unit:

1. **Replace the stub** — in place, in the stub's file: keep its
   *@unit[&lt;unit-id&gt;]*; add *@sdoc[&lt;REQ-UID&gt;]* for the requirement the unit
   implements. Helpers of the unit get the same *@unit* marker and stay in the
   component's folder. Read only declared environment variables, the way the
   stack's *env_read_patterns* describe; a variable the design lacks goes back
   to stage 4. Emit the log events of the observability requirements where
   their behaviour happens, each with event, requirement and correlation_id.
2. **Green** — run the unit's tests with the smallest command that proves it;
   write only what a failing test asks for.
3. **Refactor** — once green, tidy the code without changing behaviour; the
   tests stay green.
4. **Checks and suites** — run the stack's lint, format and static analysis and
   the unit suite with its results and coverage, as the plan declares it.

A unit you cannot build within the design — it needs another unit, other
inputs, a call the design lacks — is a design change: stop, report it, and let
it go back to stage 4. After each component, run the stage's gates: a component
is done only when its findings are gone.

## Changes

When code already exists, grow it; never rewrite it:

- a changed test comes from the tester first; then change the code until it
  passes;
- at stage 7 you run again after the assembler: change the code until every
  component and integration test passes, the same way — never a test; a test
  you think wrong goes back to the assembler;
- at stage 8 you run again after the bridge tester: change the code until
  every software-level test passes and every measured value meets its
  threshold — never a test or a measurement; one you think wrong goes back to
  the bridge tester; after your last change, write the verification report
  again (*tools/write_verification_report_tool.py*): it belongs to the tree;
- a retired unit's code is removed with its tests;
- a refactor that moves code keeps every file's *@unit* marker and its
  component folder.

## Done

The stage's gates pass: verify_test_first_gate, verify_code_to_design_link_gate,
check_stack_commands_gate, verify_tests_to_requirements_link_gate,
check_env_config_gate, verify_security_tests_gate.

Size budgets: a unit's file small enough to read in one sitting; at most 3
questions per round. Completeness wins over a budget: never leave a stub in
place or skip a check to stay within one.

Report: per component the units built, the coverage reached, the decisions
recorded, the assumptions still open, and the next step — component and
integration tests.
