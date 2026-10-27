---
name: derive_architecture_plugin
description: "Works out the architecture from the approved diagrams and requirements — the tech stack first, approved at checkpoint 3, then one component per node and one interface per edge, with a threat analysis of every trust boundary."
---

# plugin: derive_architecture_plugin

**Stage:** 3 · SWE.2 Software architecture
**Fills slot:** create_architecture_plugin
**Loaded with:** choose_stack_skill, write_design_skill, record_decisions_skill, ensure_testability_skill, create_security_tests_skill

## Goal

From the approved architecture diagrams and the approved requirements to the
tech stack, its decision record, and the architecture: the components, the
interfaces between them, and an analysis of the threats at every trust boundary.

The architecture says what the parts are and how they talk, not how each one is
built inside — that is detailed design, the next stage.

Not this method's job: the form (the rules skills loaded with it), the checks
(the stage's gates), the approvals (the architect at checkpoint 3, the reviewer
at checkpoint 4).

## Explore

Read before writing anything:

- the approved architecture diagrams — every node and edge, and which edges
  cross the system boundary;
- the approved requirements — the constraints (a given runtime, database or
  standard) and the non-functional ones with their thresholds;
- the existing stack, architecture and decision records, if any — they are the
  source of truth to grow;
- in an existing product, the code's structure and patterns. **Follow the
  patterns the product already uses** unless the change is about them; note
  where you would do it differently, but do not redesign what nobody asked to
  change.

## Ask

Ask the round in one message: 3–5 questions whose answer would change the
architecture, each a choice printed by `<framework>/agent/ask_person_tool.py` — the
readings you see as options, the last *something else: I tell you* when the
answer is one only the person knows, and the assumption you will write from
if it is skipped as the proposal — so the person accepts it with Y, picks
another, or tells their own:

- the team's skills and the technologies the organisation supports or forbids;
- hosting and operations — where it runs, how it is deployed and watched;
- data — how much, how sensitive, how long it is kept;
- integrations — the systems outside it and how much they can be trusted;
- budgets the requirements leave open — memory, cost, response time.

Never invent an answer: a constraint nobody gave you is an assumption, stated
as one.

## Depth

- **Lite** — one or two components inside one trust boundary: a short stack
  record, budgets for the components, interfaces without threat entries.
- **Full** — anything crossing the system boundary, personal or financial data,
  several teams, or criticality high: every external interface analysed for
  threats, every budget traced to a non-functional threshold.

When in doubt, full.

## Steps

The stack comes first, and is approved before anything is designed on it:

1. **Stack** — one row per tool the product takes from outside, in its area,
   an exact version each, respecting every constraint requirement: every area
   of *choose_stack_skill* either chosen or not needed with the reason, the
   areas the framework gives as it gives them, and test runners that can run
   every verification suite the requirements name.
2. **Decision record** — the stack's alternatives, at least two, with pros, cons
   and the choice.
3. **Checkpoint 3** — stop here: the stack's gates must pass and the architect
   approve the stack before any component is designed. Show the stack as the
   table *write_stack_table_tool* prints.
4. **Components** — one per node of the architecture diagrams, with its
   responsibility, its resource budget with value and unit, its size (S, M, L
   or XL), the software requirements it meets, its modes with their transitions
   and what it does in parallel — either may be *not_applicable* with the
   reason; actors outside the product as external. Every participant of a
   sequence diagram must be one of these components. Each component names its
   composition root, the one place its concrete implementations are wired.
5. **Interfaces** — one per edge, with protocol and data; external when one end
   is external. Each names the real implementation of its *to* end and a test
   double that replaces it — external ones too, where an isolated test cannot
   reach the real thing.
6. **Threats** — for every external interface, a threat table in the
   architecture file: each threat (spoofing, tampering, disclosure, denial of
   service, elevation of privilege, …) marked *applicable* with its mitigation
   and the test that will prove it, or *N/A* with the reason. An applicable
   threat's test is planned in the verification stages: name, in the
   interface's *security_templates*, the catalog templates that cover its
   threats (*create_security_tests_skill*).
7. **Decisions** — a record for every other non-obvious choice.

After each step, run the stage's gates: a task is done only when its findings
are gone.

## Changes

When a stack or architecture already exists, grow it; never rewrite it:

- a changed choice is a new decision record that supersedes the old one;
- an added, changed or removed component or interface keeps its ID, or retires
  it — an ID is never reused;
- every change states its **migration**: how the running product gets from the
  old architecture to the new one — data to move, interfaces to keep for a
  while, the order of the rollout — or that none is needed.

## Done

The stage's gates pass: check_stack_decision_gate, verify_stack_approval_gate,
check_design_contract_gate and verify_decision_records_gate.

Size budgets: a responsibility is one sentence; a decision record at most 400
words; at most 5 questions per round. Completeness wins over a budget: never
leave out a component, an interface or a threat to stay within one.

Report: the stack and its approval, the components and interfaces with their
budgets, the threats per external interface with the tests they require, the
assumptions still open, and the next step — the detailed design.
