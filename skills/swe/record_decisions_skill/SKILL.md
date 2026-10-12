---
name: record_decisions_skill
description: "Rules for decision records: one file per non-obvious architectural choice, at least two options weighed with pros and cons, the choice being one of them, and its consequences stated."
---

# skill: record_decisions_skill

**Stage:** 3 · SWE.2 Software architecture
**Loaded with:** create_architecture_plugin
**Contract:** contracts/decision_contract.v1.schema.json
**Gates:** verify_decision_records_gate

## What it governs

The decision records in *qf.yaml paths.decisions_dir*: every non-obvious choice
of the architecture — the tech stack first — written down with the alternatives
that were weighed, so a reader later knows not only what was chosen but why.

## Inputs

- The **requirements** and **constraints** that force the decision.
- The **existing decision records** — a new one supersedes an old one, it does
  not rewrite it.

## Contract

One Markdown file per decision, *NNNN-&lt;slug&gt;.md*, holding one ```yaml decision
block (*decision.v1*): *ADR-NNNN*, title, status, date, context, at least two
options with pros and cons, the choice, consequences, and the record it
supersedes, if any.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every record holds one readable block following *decision.v1* | verify_decision_records_gate · UNREADABLE_DECISION, SCHEMA_VIOLATION |
| R2 | The file name starts with the number of its ID, and an ID is used once | verify_decision_records_gate · FILE_NAME_MISMATCH, DUPLICATE_DECISION |
| R3 | The choice is one of the options | verify_decision_records_gate · CHOICE_NOT_AN_OPTION |
| R4 | A superseded record exists; a record is changed by superseding it, not by rewriting it | verify_decision_records_gate · UNKNOWN_SUPERSEDED |
| R5 | The options are real alternatives, and the consequences honest | Checkpoint 3 |

## Not checkable

That the options were genuinely considered, not added to fill the form.

## Example

```yaml decision
id: ADR-0001
title: Java 21 and Spring Boot for the auth service
status: accepted
date: 2026-10-05
context: The customer operates only Java 21 runtimes; sign-in must answer within 200 ms.
options:
  - name: Java 21 + Spring Boot
    pros: [runs on the customer's runtime]
    cons: [higher memory use]
  - name: Go
    pros: [small footprint]
    cons: [not supported by the customer's operations]
choice: Java 21 + Spring Boot
consequences: Memory budget of 256 MB per instance.
```
