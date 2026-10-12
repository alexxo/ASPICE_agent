---
name: configure_observability_skill
description: "Rules for observability definitions (principles #37-#39): every observability requirement watched by at least one alert, dashboard or health-check definition stored in the product and naming it with @sdoc; deployed with the release."
---

# skill: configure_observability_skill

**Stage:** 8 · SWE.6 Software verification
**Loaded with:** create_software_tests_plugin
**Contract:** contracts/requirement_contract.v1.schema.json
**Gates:** check_observability_gate
**Replaces:** production-observability (main)

## What it governs

The alerts, dashboards and health checks that watch the product in operation.
What watches a feature is a requirement: its observability requirement lists
the events it emits and, in *watched_by*, what watches it (stage 2). The
bridge tester writes the definitions as files in *qf.yaml
paths.observability_dir*, in the format of the product's observability
platform; each names the requirement it serves with *@sdoc[&lt;REQ-UID&gt;]* in a
comment or label. Deploying them is part of the release.

## Inputs

- The **requirements** of kind observability — their *events* and
  *watched_by*.
- The **tech stack** — the observability platform and its definition format.
- The existing definitions under *paths.observability_dir*.
- On a retry: the **findings** of the previous attempt.

## Contract

The *watched_by* and *events* of a ```yaml requirement block
(*requirement.v1*) of kind observability. Every *watched_by* entry becomes a
definition file under *paths.observability_dir* that carries
*@sdoc[&lt;REQ-UID&gt;]* and watches the requirement's events (e.g. an alert on
the rate of *auth.signin.error*).

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every observability requirement has at least one definition naming it with @sdoc | check_observability_gate · UNOBSERVED_REQUIREMENT |
| R2 | Every @sdoc marker of a definition names an existing requirement | check_observability_gate · UNKNOWN_REQUIREMENT |
| R3 | Every watched_by entry has its definition, watching the requirement's events | Checkpoint 4 |

## Not checkable

- That an alert fires when it should — tested in staging before production,
  left to the organisation.
- That the release deployed the definitions — checked with the release step.

## Example

```yaml requirement
uid: REQ-0048
level: software
kind: observability
criticality: high
statement: The auth service logs every sign-in.
acceptance_criteria:
  - case: happy
    given: a registered account
    when: the user signs in
    then: a start and an end event are logged
  - case: error
    given: a wrong password
    when: the user signs in
    then: an error event is logged
feasibility: The logging library is already part of the stack.
size: S
environment: none
derived_from: login#auth-service
refines: REQ-0012
metric: sign-ins without their end or error event
threshold: "== 0 sign-ins"
measurement_method:
  instrument: integration
  window: one run
  sample: every sign-in of the run
events: [auth.signin.start, auth.signin.end, auth.signin.error]
watched_by:
  - alert on more than 50 sign-in errors per minute
```
