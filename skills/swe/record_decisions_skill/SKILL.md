---
name: record_decisions_skill
description: "Rules for decision records: one file per non-obvious choice of the architecture or the design, at least two options weighed with pros and cons, the choice being one of them, its consequences stated; the person decides a choice a critical requirement depends on, the agent every other, written down so the person can read and change it."
---

# skill: record_decisions_skill

**Stage:** 3 · SWE.2 Software architecture; 4 · SWE.3 Software detailed design
**Loaded with:** create_architecture_plugin, create_detailed_design_plugin
**Contract:** contracts/decision_contract.v1.schema.json
**Gates:** verify_decision_records_gate

## What it governs

The decision records in *qf.yaml paths.decisions_dir*: every non-obvious choice
of the architecture — the tech stack first — and of the detailed design and the
build, written down with the alternatives that were weighed, so a reader later
knows not only what was chosen but why.

From stage 4 on, every record says who decides (*decided_by*). The person
decides only a choice a critical requirement depends on — criticality high, or
kind security: the record asks them, with a proposal, and is accepted with
their answer. The agent decides every other choice and writes it down, so the
person can read it on the decisions page and change it with one link. The
person is never asked again what they answered: a record that changes one
supersedes it, and the page shows the earlier choice as *Before*.

A record is written only for a real choice — at least two options with
different outcomes. A requirement, even a critical one, whose build leaves
nothing to choose needs no record and no card: the design and its review show
it is met.

## Inputs

- The **requirements** and **constraints** that force the decision.
- The **existing decision records** — a new one supersedes an old one, it does
  not rewrite it.

## Contract

One Markdown file per decision, *NNNN-&lt;slug&gt;.md*, holding one ```yaml decision
block (*decision.v1*): *ADR-NNNN*, title, status, date, context, at least two
options with pros and cons, the choice, consequences, and the record it
supersedes, if any.

From stage 4 on, also: *decided_by*, the *requirements* it serves, and the
*change_request* it was made for, if any —

- **decided_by: person** — the *question* (plain words, ending with ?),
  *why_you* (the critical requirement it touches), and while *proposed* the
  *choice* proposed with *proposed_because*. Ask it with
  *agent/render_decisions_tool.py --ask ADR-NNNN*, the one card; record the
  answer with *--answer Y|n --by NAME* — status *accepted*, the chosen option,
  *answered_by*.
- **decided_by: agent** — status *accepted*, *not_critical* (why no critical
  requirement depends on it) and *where* (path:line in the work).

After every change, render the decisions page,
*agent/render_decisions_tool.py*, and commit it.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every record holds one readable block following *decision.v1* | verify_decision_records_gate · UNREADABLE_DECISION, SCHEMA_VIOLATION |
| R2 | The file name starts with the number of its ID, and an ID is used once | verify_decision_records_gate · FILE_NAME_MISMATCH, DUPLICATE_DECISION |
| R3 | The choice is one of the options | verify_decision_records_gate · CHOICE_NOT_AN_OPTION |
| R4 | A superseded record exists; a record is changed by superseding it, not by rewriting it | verify_decision_records_gate · UNKNOWN_SUPERSEDED |
| R5 | The options are real alternatives, and the consequences honest | Checkpoint 3; Review |
| R6 | A record saying who decides has what its card needs: the requirements; the person's, the question, why they are asked, the proposal while proposed and who answered once accepted; the agent's, why it is not critical and where it is in the work | verify_decision_records_gate · INCOMPLETE_DECISION |
| R7 | Each requirement a record serves exists | verify_decision_records_gate · UNKNOWN_REQUIREMENT |
| R8 | The agent decides no choice a critical requirement depends on | verify_decision_records_gate · AGENT_DECIDED_CRITICAL |
| R9 | The decisions page exists and is what the records render now | verify_decision_records_gate · MISSING_DECISIONS_PAGE, DECISIONS_PAGE_OUTDATED |
| R10 | The person is asked only what a critical requirement depends on, and never again what they answered; a choice the agent made is really not critical, and is where the record says | Review |

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

A choice of the detailed design the agent made, for a change request:

```yaml decision
id: ADR-0014
title: Tags are shown in the order the editor typed them
status: accepted
date: 2026-10-29
context: REQ-0147 asks for the tags of a post to be shown under its title.
options:
  - name: the order typed
    pros: [the editor chose it]
    cons: [two posts may list the same tags differently]
  - name: alphabetical
    pros: [the same tags always read the same]
    cons: [overrides the editor's order]
choice: the order typed
consequences: No sorting step; the order is the editor's.
decided_by: agent
requirements: [REQ-0147]
not_critical: Only how tags look; rated low at checkpoint 2.
where: [src/publisher/tags.py:42, docs/design/publisher.md:118]
change_request: 37
```
