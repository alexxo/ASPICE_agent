---
name: derive_software_tests_plugin
description: "Works out a software-level test for every requirement of both levels, the measurements of the non-functional ones, the observability definitions and the software section of the verification plan, committed without code; then hands failures to the coder, who changes code until every test passes and every threshold is met."
---

# plugin: derive_software_tests_plugin

**Stage:** 8 · SWE.6 Software verification
**Fills slot:** create_software_tests_plugin
**Loaded with:** verify_software_skill, configure_observability_skill, specify_nfr_measurement_skill

## Goal

From the requirements to the tests of the whole software: for every
requirement of both levels, a test that checks its acceptance criteria on the
integrated software — a system-level one end-to-end, from outside — or, for a
non-functional one, a measurement of its metric against its threshold. Also
the alert, dashboard and health-check definitions every observability
requirement names, and the first time the software section of the
verification plan.

You are the bridge tester. You test what the requirements promise, from the
outside of the software, never its components or units: those were tested at
stages 5 to 7.

Not this method's job: changing the code (the coder, *create_unit_code_plugin*,
runs after you in this stage), the form (the rules skills loaded with it), the
checks (the stage's gates), the agreement (the reviewer at the pull request,
checkpoint 4 on a sample).

## Explore

Read before writing anything:

- every requirement — its level, kind, acceptance criteria, and for
  non-functional ones the metric, threshold and measurement method;
- the architecture's outside interfaces — where a test reaches the software;
- the tech stack — its *test_runner* rows, the tools the suites can run with;
- the verification plan, and the existing software-level tests under
  *paths.software_tests_dir* and definitions under *paths.observability_dir*
  — the source of truth to grow.

## Ask

Ask no person: from stage 4 on the build is the agents' and the gates', and
the person approves the results (checkpoint 4). Settle each question below
yourself, write the choice as an assumption in the test's docstring and the
verification plan, and go on; the reviewer agent judges every assumption:

- what the test environment holds — sample data, external services stubbed
  or real;
- how a non-functional metric is measured in this product — load, window,
  sample;
- which observability platform the definitions are written for.

Never invent an expected value or a threshold: a value nobody gave you is an
assumption, stated as one.

A question no requirement answers whose answer changes what the user sees or
gets is a question of what is wanted: never ask it in the session. Write it
in the report and the pull request: the reviewer agent sends it to the
person, whose answer changes the requirements (a change request).

## Depth

- **Lite** — no system-level and no non-functional requirement besides
  observability: one test per requirement.
- **Full** — system-level or measured requirements, or criticality high: also
  every acceptance criterion's error case, and every measurement over the
  requirement's window and sample.

When in doubt, full.

## Steps

1. **Plan** — the first time, the software section of the verification plan:
   techniques, criteria, environment, selection, regression, the order of
   suites, and the suites themselves — *software*, *e2e* and every measuring
   suite a requirement names — each with its command, its tool (a
   *test_runner* of the stack), results, *test_files* and, when it measures,
   *measurements*. Each acceptance case is tested once, from the outside, so the suite
   stays within its budget (600 s by default).
2. **Software-level tests** — per software-level requirement that is neither a
   constraint nor measured, tests of its acceptance criteria marked
   *@sdoc[&lt;REQ-UID&gt;]*, run by the *software* suite, in files matching
   the suite's *test_files* under *paths.software_tests_dir*.
3. **End-to-end tests** — the same for every system-level requirement, through
   the product's outside interfaces, run by the *e2e* suite.
4. **Measurements** — per requirement measured by a suite of this section
   (*software*, *e2e*, *bench*, *security*), a test run by that suite that
   measures the metric and writes the value, in the threshold's unit, to the
   suite's *measurements* file. A requirement measured by the *unit* or the
   *integration* suite was measured by its own stage (5 or 7); a value
   missing here is added there — an integration measurement in a commit with
   no code; a unit one cannot be written first once the unit is built, so its
   instrument changes by a change request.
5. **Observability** — per observability requirement, a definition under
   *paths.observability_dir* for every *watched_by* entry, marked
   *@sdoc[&lt;REQ-UID&gt;]*.
6. **Run** — run the suites; a test that fails or a value that misses its
   threshold because the code is wrong stays as it is: the coder fixes the
   code.
7. **Commit** — the plan, the tests and the definitions, in one commit with no
   code.
8. **Report** — once every gate but the report's passes, write the
   verification report for the tree: *tools/write_verification_report_tool.py*.

Then the coder changes the code until every test passes and every value meets
its threshold, never touching a test. After each commit, run the stage's
gates: the stage is done only when its findings are gone. A finding that a
test is wrong comes back to you.

## Changes

When tests already exist, grow them; never rewrite them:

- a new requirement gets its test or measurement in a new test-only commit;
- a changed acceptance criterion or threshold changes its test in a test-only
  commit, before the code that follows it;
- a retired requirement's tests and definitions are removed with it.

## Done

The stage's gates pass: check_verification_plan_gate, verify_test_first_gate,
verify_software_tests_to_requirements_link_gate, verify_nfr_thresholds_gate,
check_observability_gate, check_verification_report_gate.

Size budgets: one requirement per test file; at most 5 questions per round.
Completeness wins over a budget: never leave out a requirement, an acceptance
criterion, a measurement or a definition to stay within one.

Report: per requirement the test or measurement that proves it, the
definitions per observability requirement, the assumptions still open, and the
next step — the code, by the coder, until every test passes.
