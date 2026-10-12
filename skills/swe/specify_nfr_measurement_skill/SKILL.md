---
name: specify_nfr_measurement_skill
description: "Rules for non-functional requirements: a metric, a threshold with a number, and the verification suite that measures it."
---

# skill: specify_nfr_measurement_skill

**Stage:** 2 · SWE.1 Software requirements; 8 · SWE.6 (measured)
**Loaded with:** create_requirements_plugin, create_software_tests_plugin
**Contract:** contracts/requirement_contract.v1.schema.json
**Gates:** check_requirements_contract_gate, check_stack_decision_gate
**Replaces:** nfr-measurability (main)

## What it governs

The measurement fields of every requirement of a non-functional kind —
performance, security, usability, reliability, maintainability, portability,
compatibility and observability. A non-functional requirement is not a wish:
it names what is measured, the pass value, and the verification suite that
measures it, so SWE.6 can compare the result with the threshold without
interpretation. It never names a tool: at SWE.1 the tech stack is not decided
yet, and the requirement must stay true whichever stack wins.

## Inputs

- The requirement being written by *write_requirements_skill*.
- On a retry: the **findings** of the previous attempt (*findings.v1*).

## Contract

Fields of *requirement.v1* that apply to non-functional kinds:

| Field | Rule | Example |
|---|---|---|
| **metric** | One measurement, as a noun phrase; no number in it | p95 request latency |
| **threshold** | Operator (&lt;=, &gt;=, &lt;, &gt;, ==), a number, its unit or counted noun | &lt;= 200 ms |
| **measurement_method.instrument** | A verification suite: unit, integration, software, bench, security or e2e | bench |
| **measurement_method.window** | The observation window | single benchmark run |
| **measurement_method.sample** | The sample size or aggregation basis | &gt;= 10000 requests |

Kind *observability* also states:

| Field | Rule | Example |
|---|---|---|
| **events** | The log events the feature emits | auth.signin.start |
| **watched_by** | The alerts or health checks that watch it | alert on more than 50 errors per minute |

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every non-functional requirement has metric, threshold and measurement method; a functional, constraint or interface requirement has none | check_requirements_contract_gate · SCHEMA_VIOLATION |
| R2 | The threshold has an operator and a number | check_requirements_contract_gate · SCHEMA_VIOLATION |
| R3 | The instrument names a verification suite from the fixed vocabulary, never a tool | check_requirements_contract_gate · SCHEMA_VIOLATION |
| R4 | The tech stack, once decided at SWE.2, provides a command for every suite a requirement names | check_stack_decision_gate · UNKNOWN_INSTRUMENT |
| R5 | An observability requirement lists its events and what watches it | check_requirements_contract_gate · SCHEMA_VIOLATION |
| R6 | The events include a start, an end and an error event for the feature | Checkpoint 2; verified at SWE.5 by verify_log_events_gate |
| R7 | The threshold's unit is the unit the suite reports | Checkpoint 3 |
| R8 | At SWE.6 the instrument's suite writes the measured value, in the threshold's unit, to its measurements file, and the value meets the threshold | Checkpoint 4; verified at SWE.6 by verify_nfr_thresholds_gate |

## Not checkable

- Whether the threshold is the right value for the product.
- Whether the suite really measures the metric (R7) — the architect checks it
  when approving the stack.

## Example

```yaml requirement
uid: REQ-0060
level: software
kind: performance
criticality: medium
statement: The auth component answers a sign-in request within 200 ms at the 95th percentile.
acceptance_criteria:
  - case: happy
    given: 1000 sign-in requests per second
    when: the benchmark runs
    then: the p95 latency is at most 200 ms
feasibility: Single indexed lookup per request; no external call on the hot path.
size: M
environment:
  - element: auth database
    impact: about 1000 indexed reads per second at peak
derived_from: login#auth-service
refines: REQ-0012
metric: p95 sign-in latency
threshold: "<= 200 ms"
measurement_method:
  instrument: bench
  window: single benchmark run
  sample: ">= 10000 requests at 1000 rps"
```
