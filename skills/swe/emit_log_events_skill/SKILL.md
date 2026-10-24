---
name: emit_log_events_skill
description: "Rules for log events (principle #22): the code emits every event an observability requirement lists, each carrying the event name, the requirement UID and a correlation ID; and a passing integration test, marked with the requirement's @sdoc, names every one of its events."
---

# skill: emit_log_events_skill

**Stage:** 6 · SWE.3 unit construction (emitted); 7 · SWE.5 (asserted)
**Loaded with:** create_unit_code_plugin, create_integration_tests_plugin
**Contract:** contracts/requirement_contract.v1.schema.json
**Gates:** verify_log_events_gate

## What it governs

The log events the product emits. Which events a feature emits is a
requirement: every feature has one of kind *observability* (stage 2), whose
*events* list them — typically a start, an end and an error event. The coder
emits them where the requirement's behaviour happens (stage 6); the assembler
asserts them in an integration test, and the coder fixes what is missing
(stage 7).

## Inputs

- The **requirements** of kind observability — their *events* and acceptance
  criteria.
- The **detailed design** — the unit where each event's behaviour starts, ends
  or fails.
- The **tech stack** — its logging library.
- On a retry: the **findings** of the previous attempt.

## Contract

The *events* of a ```yaml requirement block (*requirement.v1*) of kind
observability. Every event the code emits carries three fields:

- **event** — the name, exactly as the requirement lists it
  (e.g. *auth.signin.end*);
- **requirement** — the UID of the observability requirement (e.g. *REQ-0048*);
- **correlation_id** — the same value on every event of one request, so the
  start, end and error of one sign-in can be found together.

An integration test asserting them carries *@sdoc[&lt;REQ-UID&gt;]* and names
every event of the requirement literally.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every event of every observability requirement is named by a passing integration test carrying the requirement's @sdoc marker | verify_log_events_gate · UNTESTED_EVENT |
| R2 | The code emits each event where its behaviour happens, with event, requirement and correlation_id; no secret or personal data beyond an ID | Checkpoint 4 |

## Not checkable

The reviewer agent at the pull request, and a person on the important or
risky pull requests (checkpoint 4), confirm:

- The test really captures the emitted events and checks them — not merely
  that their names appear in the test.
- Each event carries the three fields, and the error event is emitted on every
  failure path.
- No event logs a secret, a password or personal data beyond an ID.

## Example

```yaml requirement
uid: REQ-0048
level: software
kind: observability
criticality: medium
statement: The auth component logs every sign-in attempt and its outcome.
acceptance_criteria:
  - case: happy
    given: any sign-in attempt
    when: it completes
    then: one auth.signin.end or auth.signin.error event is logged with the account ID
feasibility: Structured logger already in the stack.
size: S
environment:
  - element: log pipeline
    impact: about 3 events per sign-in
derived_from: login#auth-service
refines: REQ-0012
metric: sign-in attempts with a matching end or error event
threshold: "== 100 %"
measurement_method:
  instrument: integration
  window: one test run
  sample: every acceptance criterion of REQ-0047
events:
  - auth.signin.start
  - auth.signin.end
  - auth.signin.error
watched_by:
  - alert on more than 50 auth.signin.error events per minute
```
