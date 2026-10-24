---
name: write_detailed_design_skill
description: "Rules for the detailed design of SWE.3: per component its units from the component's design diagram, every input and output with type, range and unit of measure, calls inside the component, and calls, structure edges and interactions that agree."
---

# skill: write_detailed_design_skill

**Stage:** 4 · SWE.3 Software detailed design and unit construction — design (BP1, BP2)
**Loaded with:** create_detailed_design_plugin, and create_diagram_plugin for the design diagrams
**Contract:** contracts/unit_contract.v1.schema.json
**Gates:** check_detailed_design_contract_gate

## What it governs

The detailed design, in *qf.yaml paths.detailed_design_dir*: for every component
of the architecture, the software units it is made of, their inputs and outputs,
how they call each other, and two diagrams that show the same. The diagram
plugin (e.g. Archify) draws the diagrams; this skill says what the framework
needs from them. A design is agreed at the pull request, not at a checkpoint,
so the gates are what keeps it consistent.

## Inputs

- The **architecture** — the components and interfaces in
  *paths.architecture_dir*; external actors get no detailed design.
- The **approved requirements** and the **approved tech stack**, for the types
  each unit uses.
- The **existing detailed design**, if any — a feature amends the documents of
  the components it touches, it does not redraw them.
- On a retry: the **findings** of the previous attempt.

## Contract

Per component, in *paths.detailed_design_dir*, three files named after its ID:

| File | Contract | Holds |
|---|---|---|
| *&lt;component-id&gt;.md* | *unit.v1*, one ```yaml unit block per unit | The units: the node each comes from, responsibility, inputs and outputs with type, range and unit of measure, the units it calls |
| *&lt;component-id&gt;.architecture.json* | the diagram tool's own, read through the adapter | The structure: one node per unit, one edge per call |
| *&lt;component-id&gt;.sequence.json* | the diagram tool's own, read through the adapter | The interactions: every relevant one, in one diagram, between the component's units |

A unit is referenced as *&lt;component-id&gt;#&lt;unit-id&gt;*; code and tests name
it as *@unit[&lt;unit-id&gt;]*, so a unit ID is unique in the product. A numeric
input or output has a range *{min, max}* and a real unit of measure (e.g.
*count*, *ms*); any other has *not applicable* for both.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every component of the architecture has its detailed design, and every detailed design belongs to a component; externals have none | check_detailed_design_contract_gate · NO_DETAILED_DESIGN, MISSING_DETAILED_DESIGN, UNKNOWN_COMPONENT |
| R2 | Every unit block can be read and follows its contract | check_detailed_design_contract_gate · UNREADABLE_BLOCK, SCHEMA_VIOLATION |
| R3 | A unit ID is used once in the product | check_detailed_design_contract_gate · DUPLICATE_ID |
| R4 | Every component has its structure diagram, and its sequence diagram once any unit calls another; each can be read, every element has an ID and a label, and every edge and message connects nodes that exist | check_detailed_design_contract_gate · MISSING_DESIGN_DIAGRAM, INVALID_DIAGRAM_ID, UNREADABLE_DIAGRAM, UNSUPPORTED_DIAGRAM_TYPE, EMPTY_DIAGRAM, MISSING_ID, MISSING_LABEL, MISSING_ENDPOINT, DANGLING_ENDPOINT |
| R5 | Every unit derives from a node of its own component's structure diagram, and every node of that diagram is a unit | check_detailed_design_contract_gate · UNKNOWN_ELEMENT, UNCOVERED_NODE |
| R6 | A unit calls only units of the same component | check_detailed_design_contract_gate · UNKNOWN_UNIT |
| R7 | A range's minimum is not above its maximum | check_detailed_design_contract_gate · INVALID_RANGE |
| R8 | Every participant of the component's sequence diagram is one of its units | check_detailed_design_contract_gate · UNKNOWN_PARTICIPANT |
| R9 | Every call appears as a message between the two units, and every message between units is a declared call or the reply to one | check_detailed_design_contract_gate · UNSHOWN_CALL, UNDECLARED_CALL |
| R10 | Every call is an edge of the structure diagram, and every edge between units is a declared call | check_detailed_design_contract_gate · UNDRAWN_CALL, UNDECLARED_EDGE |
| R11 | Every environment variable a unit will read is declared once, in its contract (validate_env_config_skill) | check_detailed_design_contract_gate · UNREADABLE_BLOCK, SCHEMA_VIOLATION, DUPLICATE_VARIABLE |
| R12 | The interactions agree with the architecture's flows, units are cohesive, and an input declared not numeric really is not | Checkpoint 4 |

## Not checkable

The reviewer agent confirms at the pull request, and a person on the
important or risky pull requests (checkpoint 4):

- The interactions agree with the architecture's flows and the component's
  responsibility — no unit does work that belongs to another component.
- Each unit has one responsibility; a unit is not split or merged to dodge a
  rule.
- The ranges and units of measure are the real ones, and *not applicable* is
  used only for values that are not numeric.

## Example

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
