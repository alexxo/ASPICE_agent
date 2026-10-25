---
name: derive_detailed_design_plugin
description: "Works out the detailed design of every component from the architecture — its units with their inputs and outputs, ranges and units of measure, the calls between them, and the structure and sequence diagrams drawn by the diagram plugin."
---

# plugin: derive_detailed_design_plugin

**Stage:** 4 · SWE.3 Software detailed design and unit construction — design (BP1, BP2)
**Fills slot:** create_detailed_design_plugin
**Loaded with:** write_detailed_design_skill, validate_env_config_skill

## Goal

From the architecture to the detailed design of every component: the software
units it is made of, what each takes and gives — with type, valid range and unit
of measure — which units call which, and two diagrams that show the same: the
structure (one node per unit, one edge per call) and, once a unit calls another,
the interactions.

The detailed design says how each component is built inside, not the code —
that is the next stage, unit by unit, test first.

Not this method's job: the form (the rules skill loaded with it), the drawing
(the diagram plugin, loaded at this stage too), the checks (the stage's gate),
the agreement (the reviewer at the pull request, checkpoint 4 on a sample).

## Explore

Read before writing anything:

- the architecture — every component of role component, its responsibility,
  budget, modes and composition root, and every interface it offers or uses;
- the approved requirements each component meets, with their acceptance
  criteria: each behaviour must land in some unit;
- the approved tech stack, for the types and the language's conventions;
- the existing detailed design, if any — the source of truth to grow;
- in an existing product, **the code that will be affected: its entry points,
  structure, patterns and test infrastructure**. Follow the patterns the product
  already uses unless the change is about them.

## Ask

Ask no person: from stage 4 on the build is the agents' and the gates', and
the person approves the results (checkpoint 4). Settle each question below
yourself, write the choice as an assumption in the design, as a decision of
its own (`D<n> — assumed: …`), and go on; the reviewer agent judges every
assumption:

- the limits the requirements leave open — sizes, counts, durations, the
  range of every numeric input;
- what must stay separate — pieces that change for different reasons, or that
  another team owns;
- reuse — an existing unit or library the design should call rather than build.

Never invent a range: a limit nobody gave you is an assumption, stated as one.

A question no requirement answers whose answer changes what the user sees or
gets is a question of what is wanted: never ask it in the session. Write it
as a step the design leaves open, so its story shows it as a gap (⚠): the
reviewer agent sends a gap no requirement answers to the person.

## Depth

- **Lite** — a component of one or two units with no numeric input: the units,
  a structure diagram, no sequence diagram while no unit calls another.
- **Full** — several units calling each other, numeric inputs and outputs, or
  a component meeting a requirement of criticality high: every range traced to
  a requirement or an assumption, every call shown in both diagrams.

When in doubt, full.

## Steps

One component at a time, every component of role component:

1. **Units** — split the component into units, each with one responsibility; an
   ID unique in the product, because code and tests will name it as
   *@unit[&lt;id&gt;]*.
2. **Inputs and outputs** — for every unit, each input and output with its type
   in the stack's language; a numeric one with its valid range and unit of
   measure, any other *not applicable* for both.
3. **Calls** — which units of the same component each unit calls. A call to
   another component goes through the architecture's interface, not to its
   units.
4. **Structure diagram** — ask the diagram plugin for
   *&lt;component-id&gt;.architecture.json*: one node per unit, one edge per call;
   then derive every unit from its node.
5. **Sequence diagram** — once any unit calls another, ask the diagram plugin
   for *&lt;component-id&gt;.sequence.json*: every relevant interaction between the
   component's units, every call shown as a message and no message that is not
   a call.
6. **Settings** — every value a unit needs from where it runs (a URL, a secret,
   a limit an operator may change) is an environment variable, declared in
   *paths.env_variables_file*: description, required, an example that is never
   a real secret, and its valid values.

After each component, run the stage's gate: a component is done only when its
findings are gone.

## Changes

When a detailed design already exists, grow it; never rewrite it:

- a feature amends the documents and diagrams of the components it touches,
  and only those;
- an added, changed or removed unit keeps its ID, or retires it — an ID is
  never reused, because code and tests name it;
- a changed input or output range states what happens to values that were
  valid before.

## Done

The stage's gate passes: check_detailed_design_contract_gate, which also checks the
environment variables' declarations.

Size budgets: a responsibility is one sentence; at most 5 questions per round.
Completeness wins over a budget: never leave out a unit, a call or an
interaction to stay within one.

Report: the units per component with their numeric ranges, the calls, the
assumptions still open, and the next step — the code, unit by unit, test first.
