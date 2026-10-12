---
name: write_design_skill
description: "Rules for the software architecture of SWE.2: one component per node and one interface per edge of the approved architecture diagram, a resource budget, size, modes and concurrency for every component, every sequence participant a component, and every software requirement met by a component."
---

# skill: write_design_skill

**Stage:** 3 · SWE.2 Software architecture
**Loaded with:** create_architecture_plugin
**Contract:** contracts/component_contract.v1.schema.json
**Gates:** check_design_contract_gate

## What it governs

The architecture, in *qf.yaml paths.architecture_dir*: the components and the
interfaces between them, derived from the approved architecture diagram and the
approved requirements. Each element of the diagram becomes one element of the
architecture, so the two never drift apart.

## Inputs

- The **approved architecture diagrams** — their nodes and edges.
- The **approved requirements**, so every one is met by a component.
- The **approved tech stack** and the **decision records**.

## Contract

Markdown files whose fenced blocks are the contract:

- one ```yaml component block per node (*component.v1*): the node it comes
  from, its responsibility, its resource budget with value and unit, its size
  (S, M, L or XL), the requirements it meets, its modes with their transitions
  and its concurrency (each may be *not_applicable* with the reason) — or
  *role: external* for an actor outside the product;
- one ```yaml interface block per edge (*interface.v1*): the edge it comes from,
  from and to, external or internal, protocol, data — and, when external, the
  security test templates its boundary needs (*create_security_tests_skill*).

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | There is an architecture, and every block can be read and follows its contract | check_design_contract_gate · NO_ARCHITECTURE, UNREADABLE_BLOCK, SCHEMA_VIOLATION |
| R2 | A component or interface ID is used once | check_design_contract_gate · DUPLICATE_ID |
| R3 | Every component derives from a node and every interface from an edge of an architecture diagram | check_design_contract_gate · UNKNOWN_ELEMENT |
| R4 | Every node of an architecture diagram is a component, and every edge an interface | check_design_contract_gate · UNCOVERED_NODE, UNCOVERED_EDGE |
| R5 | An interface connects components that exist, and is external exactly when one end is external | check_design_contract_gate · UNKNOWN_COMPONENT, EXTERNAL_MISMATCH |
| R6 | Every software requirement is met by a component, and a component meets only requirements that exist | check_design_contract_gate · UNMET_REQUIREMENT, UNKNOWN_REQUIREMENT |
| R7 | A component names only decision records that exist | check_design_contract_gate · UNKNOWN_DECISION |
| R8 | Every participant of a sequence diagram is a node of an architecture diagram, so a component | check_design_contract_gate · UNKNOWN_PARTICIPANT |
| R9 | A mode moves only to modes of the same component | check_design_contract_gate · UNKNOWN_MODE |
| R10 | Responsibilities do not overlap, trust boundaries and cross-cutting concerns are covered, budgets are realistic | Checkpoint 4 |

## Not checkable

The reviewer confirms at the pull request (checkpoint 4) that responsibilities
do not overlap, that security and observability are covered, and that the
budgets add up to the non-functional thresholds.

## Example

```yaml component
id: auth-service
derived_from: auth-flow#auth-service
role: component
name: Auth service
responsibility: Checks credentials, opens sessions and locks accounts after failed sign-ins.
budget:
  - {resource: response time p95, value: 200, unit: ms}
size: M
meets: [REQ-0011, REQ-0012]
decisions: [ADR-0001]
modes:
  - {mode: start-up, to: [normal]}
  - {mode: normal, to: [degraded]}
  - {mode: degraded, to: [normal]}
concurrency: Sign-ins run in parallel; the failure counter of an account is updated atomically.
composition_root: AuthServiceApp.main
```
