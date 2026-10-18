---
name: derive_integration_tests_plugin
description: "Works out the component tests of every component and the integration tests of every approved sequence diagram, with the integration section of the verification plan, committed without code; then hands failures to the coder, who changes code until every test passes."
---

# plugin: derive_integration_tests_plugin

**Stage:** 7 · SWE.5 Software component verification and integration verification
**Fills slot:** create_integration_tests_plugin
**Loaded with:** verify_integration_skill, emit_log_events_skill

## Goal

From the architecture and the approved flows to the tests of the big pieces:
one or more component tests per component, through its own interfaces with
the declared test doubles on the other side, and one or more integration tests
per approved sequence diagram, following its messages across the real
components. The flows' tests also assert the log events of the observability
requirements. The first time, also the integration section of the
verification plan.

You are the assembler. You test what the architecture promises, through the
interfaces, never a unit's insides: a component test that reaches past an
interface tests the code instead of the component.

Not this method's job: changing the code (the coder, *create_unit_code_plugin*,
runs after you in this stage), the form (the rules skills loaded with it), the
checks (the stage's gates), the agreement (the reviewer at the pull request,
checkpoint 4 on a sample).

## Explore

Read before writing anything:

- the architecture — the components of role component, their interfaces with
  the real implementation and test double of each, and their composition roots;
- the approved sequence diagrams under *paths.diagrams_dir* — each one is a
  flow to test — and their invariants;
- the requirements each component meets, and every requirement of kind
  observability with its *events*;
- the tech stack — the integration suite's command, *integration_test_files*;
- the verification plan, and the existing component and integration tests
  under *paths.integration_tests_dir* — the source of truth to grow;
- the code only through the entry points the composition roots name.

## Ask

Ask the round in one message: 3–5 questions whose answer would change a test
or the order, each with the assumption you will write from if it is skipped:

- what must be running, or stubbed, before a step — a database, an external
  service;
- the order in which the components are integrated, when the architecture
  allows more than one;
- how a log event can be captured in the product's tests.

Never invent an expected value: a result nobody gave you is an assumption,
stated as one.

## Depth

- **Lite** — one sequence diagram and no external interface: one component
  test per component, one integration test per flow.
- **Full** — several flows, an external interface, or a requirement of
  criticality high: also each flow's error path and every invariant of the
  flow.

When in doubt, full.

## Steps

1. **Plan** — the first time, the integration section of the verification
   plan: techniques, criteria, infrastructure, regression, and the order of
   steps, each with its components, preconditions and selection. Each test
   covers an interaction once, never a rule a unit test already shows, so the
   suite stays within its budget (300 s by default).
2. **Component tests** — per component, tests through its own interfaces with
   the test doubles the architecture declares, marked
   *@component[&lt;component-id&gt;]*, in files matching *integration_test_files*
   under *paths.integration_tests_dir*.
3. **Integration tests** — per approved sequence diagram, tests that follow its
   messages across the real components, marked
   *@flow[&lt;sequence-diagram-id&gt;]*. For every observability requirement of
   the flow, a test marked *@sdoc[&lt;REQ-UID&gt;]* that captures and asserts each
   of its events by name.
4. **Run** — run the integration suite; a test that fails because the code is
   wrong stays as it is: the coder fixes the code.
5. **Commit** — the plan and the tests, in one commit with no code.

Then the coder changes the code until every test passes, never touching a
test. After each commit, run the stage's gates: the stage is done only when
its findings are gone. A finding that a test is wrong comes back to you.

## Changes

When tests already exist, grow them; never rewrite them:

- a new component or flow gets its tests in a new test-only commit;
- a changed interface or message changes its tests in a test-only commit,
  before the code that follows it;
- a retired component or flow's tests are removed with it, and the order and
  selections updated.

## Done

The stage's gates pass: check_verification_plan_gate, verify_test_first_gate,
verify_tests_to_components_link_gate, verify_tests_to_flows_link_gate,
verify_log_events_gate.

Size budgets: one flow per test file; at most 5 questions per round.
Completeness wins over a budget: never leave out a component, a flow, an
interface or an event to stay within one.

Report: per component and flow the tests and what each covers, the order, the
assumptions still open, and the next step — the code, by the coder, until
every test passes.
