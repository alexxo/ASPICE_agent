---
name: derive_unit_tests_plugin
description: "Works out, component by component and without reading the code, the unit tests from the acceptance criteria and the detailed design's ranges, one stub per unit, and the unit section of the verification plan, committed together so every new test fails."
---

# plugin: derive_unit_tests_plugin

**Stage:** 5 · SWE.4 Software unit verification — unit tests first (BP1)
**Fills slot:** create_unit_tests_plugin
**Loaded with:** enforce_test_first_skill, validate_env_config_skill, create_security_tests_skill

## Goal

From the requirements and the detailed design to the unit tests of every
component, written before any code exists: one test per acceptance criterion
of the requirements the component meets, one per range limit of every input,
and one stub per unit so the tests compile and fail. The first
time, also the unit section of the verification plan.

You are the tester. You never read the code: a test that knows the code tends
to confirm what the code does instead of what the requirement asks.

Not this method's job: the code (the next stage, by another plugin), the form
(the rules skill loaded with it), the checks (the stage's gates), the agreement
(the reviewer at the pull request, checkpoint 4 on a sample).

## Explore

Read before writing anything:

- the approved requirements, and for each component the requirements it meets
  (*meets* in the architecture), with their acceptance criteria — every *Given /
  When / Then* becomes a test;
- the detailed design of the component — its units, their inputs and outputs
  with type, range and unit of measure, and their calls;
- the architecture's interfaces and their test doubles, for the calls that
  leave the component;
- the tech stack — the language and the *test_runner* rows;
- the existing verification plan and unit tests, if any — the source of truth
  to grow;
- **not** the code under *paths.code_dir*, other than the tests and stubs you
  write.

## Ask

Ask no person: from stage 4 on the build is the agents' and the gates', and
the person approves the results (checkpoint 4). Settle each question below
yourself, write the choice as an assumption in the test's docstring and the
verification plan, and go on; the reviewer agent judges every assumption:

- what *just outside* a range must do — reject with an error, clamp, or ignore;
- an acceptance criterion whose *Then* can be observed in more than one way;
- the minimum coverage and its metric, the first time the plan is written.

Never invent an expected value: a result nobody gave you is an assumption,
stated as one.

A question no requirement answers whose answer changes what the user sees or
gets is a question of what is wanted: never ask it in the session. Write it
in the report and the pull request: the reviewer agent sends it to the
person, whose answer changes the requirements (a change request).

## Depth

- **Lite** — a component whose units have no numeric input and meet only
  requirements of criticality low: one test per acceptance criterion.
- **Full** — numeric inputs, or a requirement of criticality medium or high:
  also every range limit (min, max, just outside), and every error case of the
  acceptance criteria.

When in doubt, full.

## Steps

The first time, write the unit section of the verification plan, with its
*unit* suite: the command, its tool (a *test_runner* of the stack), where it
writes its results and coverage, and the *test_files* that tell a test from
code; a
*time_budget* only when the architect asks for a tighter one than the default
(120 s for the suite, 0.5 s per test). Each unit test tests one unit's logic
with test doubles — no database, network, process or clock. Then one
component at a time, every component of role component:

1. **Test list** — for every unit, the acceptance criteria it serves and the
   limits of its inputs: that list is what the tests must cover.
2. **Stubs** — one per unit, in a folder named after the component: the unit's
   signature from its inputs and outputs, a default return (*0*, *false*,
   empty, *null*) and nothing else, marked *@unit[&lt;unit-id&gt;]*.
3. **Tests** — one per item of the list, in files matching *test_files*, in the
   component's folder, marked *@unit[&lt;unit-id&gt;]*; calls that leave the unit
   go to test doubles. For every required environment variable the component
   reads, a test showing start-up stops when it is missing or invalid, also
   marked *@env[&lt;NAME&gt;]*. For every template an external interface into the
   component names, tests of the unit that receives what crosses it, showing
   what the catalog asks, also marked *@security[&lt;template&gt;]*.
4. **Red run** — run the unit suite: it must compile and write its results,
   and every new test must fail or error on the stubs; none may pass. A test
   that passes against a stub tests nothing; a suite that does not compile
   proves nothing — fix either before committing.
5. **Commit** — the component's tests, its stubs and, the first time, the plan,
   in one commit with no other code.

After each commit, run the stage's gates: a component is done only when its
findings are gone. A finding from stage 6 that a test is wrong comes back here.

## Changes

When tests already exist, grow them; never rewrite them:

- a new unit gets its stub and tests in a new test-only commit;
- a changed acceptance criterion or range changes its test in a test-only
  commit, before the code that follows it;
- a retired unit's tests and stub are removed with the unit.

## Done

The stage's gates pass: verify_test_first_gate, check_verification_plan_gate.

Size budgets: one assertion idea per test; at most 5 questions per round.
Completeness wins over a budget: never leave out a criterion, a limit or a unit
to stay within one.

Report: per component the tests and what each covers, the assumptions still
open, and the next step — the code, by the coder, until every test passes.
