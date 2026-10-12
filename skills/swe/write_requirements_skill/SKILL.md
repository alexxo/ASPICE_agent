---
name: write_requirements_skill
description: "Rules for SWE.1 requirement files: the requirement contract, the rules across requirements, and which gate checks each rule."
---

# skill: write_requirements_skill

**Stage:** 2 · SWE.1 Software requirements
**Loaded with:** create_requirements_plugin
**Contract:** contracts/requirement_contract.v1.schema.json
**Gates:** check_requirements_contract_gate, verify_requirements_to_diagram_link_gate, check_glossary_gate
**Replaces:** requirements-authoring (main)

## What it governs

The requirement files the agent writes at SWE.1. The plugin brings the method
— how to explore the scope and which questions to ask. This skill brings the
form the result must take and the rules it must follow. When the plugin's own
format disagrees with this skill, this skill wins: the gates accept only the
contract.

## Inputs

- The **approved diagrams** — their element lists (*diagram.v1*): the
  architecture diagrams for system-level requirements, the feature's sequence
  diagram for software-level requirements. A diagram without a recorded
  checkpoint-1 approval (*approval.v1*) is not an input.
- The **customer's wishes** (*W-01*, *W-02*, …) — the origin of constraint
  requirements the diagram cannot show (e.g. *must run on Java 21*).
- **qf.yaml** — *paths.requirements_dir* and *paths.glossary_file*.
- The **existing requirements**, so UIDs stay unique and Refines targets exist.
- On a retry: the **findings** of the previous attempt (*findings.v1*). Fix
  exactly what they name.

## Contract

- One Markdown file per feature under *paths.requirements_dir*. Headings and
  prose are free; only the fenced *yaml requirement* blocks are the contract.
- Each block is one requirement and validates against *requirement.v1*.

Fields, in the order to write them:

| Field | Rule |
|---|---|
| **uid** | *REQ-* plus at least four digits; the next free number |
| **level** | *system* or *software* |
| **kind** | functional, constraint, interface, or a non-functional category |
| **criticality** | high, medium or low — the impact if it is not met |
| **statement** | One sentence, on one line; domain terms marked *_term_* |
| **acceptance_criteria** | At least one *case* / *given* / *when* / *then*; *case* is happy, edge or error |
| **feasibility** | Whether it can be implemented, and under what conditions |
| **size** | S, M, L or XL |
| **environment** | *none*, or each element touched with its impact |
| **derived_from** | *&lt;diagram&gt;#&lt;element-id&gt;*; for kind *constraint* only, the wish that imposes it, *W-&lt;n&gt;* |
| **refines** | Software level only: the UID of one system-level requirement |

Non-functional kinds add *metric*, *threshold* and *measurement_method* —
see *specify_nfr_measurement_skill*. Kind *observability* also adds *events*
and *watched_by*.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | There is at least one requirement; every block can be read and validates against *requirement.v1*; nothing outside a block counts | check_requirements_contract_gate · NO_REQUIREMENTS, UNREADABLE_REQUIREMENT, SCHEMA_VIOLATION |
| R2 | Every UID is used once across all requirement files | check_requirements_contract_gate · DUPLICATE_UID |
| R3 | Every node, edge and invariant of an approved diagram produces at least one requirement | verify_requirements_to_diagram_link_gate · UNCOVERED_ELEMENT, DIAGRAM_UNREADABLE |
| R4 | Every *derived_from* names a diagram element, or a wish, that exists | verify_requirements_to_diagram_link_gate · UNKNOWN_DIAGRAM, UNKNOWN_ELEMENT, UNKNOWN_WISH |
| R5 | Only a requirement of kind *constraint* may derive from a wish; every other kind derives from a diagram element | check_requirements_contract_gate · SCHEMA_VIOLATION |
| R6 | Every *refines* names an existing system-level requirement (so the tree has one level, and no cycle or self-reference can occur) | check_requirements_contract_gate · UNKNOWN_PARENT, PARENT_NOT_SYSTEM |
| R7 | Every system-level requirement is refined by at least one software-level requirement | check_requirements_contract_gate · UNREFINED_SYSTEM_REQUIREMENT |
| R8 | Every feature — every sequence diagram — has at least one requirement of kind *observability* derived from one of its elements; components are checked once they exist, at SWE.2 | check_requirements_contract_gate · MISSING_OBSERVABILITY |
| R9 | Every requirement has a criterion of case *happy* | check_requirements_contract_gate · MISSING_HAPPY_CASE |
| R10 | Every requirement of criticality *high* also has a criterion of case *edge* or *error* — what goes wrong first is what an LLM leaves out | check_requirements_contract_gate · MISSING_ERROR_CASE |
| R11 | Every domain term in a statement or criterion is marked *_term_* and defined in the glossary — see *define_glossary_terms_skill* | check_glossary_gate · UNDEFINED_TERM, UNMARKED_TERM, ALIAS_USED |
| R12 | Each message of the sequence diagram produces at least one acceptance criterion | Checkpoint 2 |
| R13 | System-level requirements derive from architecture diagrams; software-level ones from the feature's sequence diagram | Checkpoint 2 |
| R14 | Write only requirement files. Never edit a diagram, an invariants file, an approval or *qf.yaml* | Checkpoint 2 |
| R15 | Each requirement states one behaviour; two behaviours are two requirements | Checkpoint 2 |

## Not checkable

The architect confirms these at checkpoint 2, after the gates pass:

- Each acceptance criterion says what its diagram message means.
- The feasibility notes are right, and the environment analysis is complete.
- The requirement says what was meant — the wording, not only the form.
- Each requirement holds one behaviour, and every domain term is marked — new
  terms included, which no gate can recognise.

## Example

```yaml requirement
uid: REQ-0047
level: software
kind: security
criticality: high
statement: The auth component locks an _account_ after five consecutive failed sign-ins.
acceptance_criteria:
  - case: happy
    given: a user with 4 failed sign-ins
    when: a 5th sign-in fails
    then: the _account_ is in _lockout_
  - case: edge
    given: an _account_ in _lockout_
    when: the correct password is submitted
    then: the sign-in is refused
feasibility: Failure counter kept in the session store, reset on success.
size: S
environment:
  - element: session store
    impact: one counter key per account, expiring after 24 h
derived_from: login#INV-1
refines: REQ-0012
metric: failed sign-ins accepted before lockout
threshold: "<= 5"
measurement_method:
  instrument: integration
  window: one test run
  sample: 10 accounts
```
