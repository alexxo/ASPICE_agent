---
name: track_nonconformances_skill
description: "Rules for the faults quality assurance leaves open (SUP.1 BP5–BP7) and the lessons of each release (principle #41): every non-conformance an issue that names where it was found and, before it closes, the pull request that fixed it; escalated once it is too old; counted per release; and every retrospective action followed up by its due date."
---

# skill: track_nonconformances_skill

**Stage:** 9 · SUP.1 Quality assurance — the issues are recorded at review, checked at release (stage 11)
**Loaded with:** review_pull_request_plugin
**Contract:** contracts/nonconformance_contract.v1.schema.json
**Gates:** check_nonconformances_gate, check_escalations_gate, report_quality_trends_gate, check_retro_actions_gate

## What it governs

What happens to a fault no gate caught and nobody fixed in its pull request:
it becomes a fault note (a non-conformance issue) that cannot be forgotten.
Also the lesson cards (retrospective actions) written after each release.

## Inputs

- **The issues** labelled *non-conformance* and *retro-action* on the code
  host.
- **qf.yaml** — *escalate_after_days*, how long a non-conformance may stay
  open.
- **The proposed release** — these rules are checked while a release record
  has no tag yet (*record_baseline_skill*).

## Contract

A non-conformance is an issue labelled *non-conformance* whose body holds one
fenced block naming the pull request it was found in:

    ```yaml nonconformance
    found_in: 41
    ```

Before it is closed, add *fixed_by*: the merged pull request that fixed it.
Once it is older than *escalate_after_days*, label it *escalated* and assign
it to a person who can decide.

A retrospective action is an issue labelled *retro-action* whose body holds

    ```yaml retro_action
    owner: lead-bob
    due: 2026-11-15
    ```

By its due date it is closed, or rescheduled by moving *due*.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | At release, every closed non-conformance has its block and names the merged pull request that fixed it | check_nonconformances_gate · NONCONFORMANCE_WITHOUT_FIX |
| R2 | At release, every open non-conformance older than escalate_after_days is labelled escalated and assigned | check_escalations_gate · UNESCALATED_NONCONFORMANCE |
| R3 | While a release is proposed, the report counts the non-conformances opened, closed and escalated since the previous release | report_quality_trends_gate · MISSING_TREND_SECTION |
| R4 | At release, no open retrospective action is past its due date, and each has its block | check_retro_actions_gate · OVERDUE_RETRO_ACTION |
| R5 | A fault found outside a gate and not fixed in its pull request becomes a non-conformance | Checkpoint 4 |

## Not checkable

- That an escalation leads to a decision, and that anyone acts on the trends
  — left to the organisation.

## Example

```yaml nonconformance
found_in: 41
fixed_by: 44
```
