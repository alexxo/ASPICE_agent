# plugins

The framework's **method skills**: one per stage, each filling the stage's slot
in `qf.yaml`. A method says **how** to work a stage's work product out; the
stage's rules skills (`skills/`) say what a correct one looks like, and the gates
(`gates/`) check it. A team may fill a slot with its own method instead.

Every method skill follows the standard in
`docs/Quality_framework_documentation.md` § *Method skills — the schema*, enforced
by `tests/consistency/test_plugins.py`. It follows ODD: Explore, Ask, Steps and
Done carry ODD's steps 2, 3, 6 and 7; the orchestrator does steps 1, 4 and 5
(Authorize, Classify, Track before write) once for every stage.

## Skeleton

Copy to `plugins/<group>/<name>/SKILL.md`, where `<group>` is the ASPICE process
group (`swe`, `sup`, `val`) and `<name>` is `action_what_plugin`. Stage, Fills
slot and Loaded with must match the stage in `agent/stages.yaml`.

```markdown
---
name: <action_what_plugin>
description: "<One line — what it produces, from what. Keep the quotes: a colon breaks YAML without them.>"
---

# plugin: <action_what_plugin>

**Stage:** <number> · <process, as in agent/stages.yaml>
**Fills slot:** <the stage's slot>
**Loaded with:** <the stage's rules skills, comma-separated>

## Goal

From <inputs> to <work product>. Behaviour, not implementation. Not this
method's job: the form (the rules skills), the checks (the gates), the approval
(the checkpoint).

## Explore

What to read before writing: the inputs, the existing work product, earlier
findings.

## Ask

The question areas of this stage. Ask one round in one message: 3–5
questions, each with the assumption used if it is skipped. Never invent an
answer.

## Depth

When the work is lite, and when it is full, by risk.

## Steps

The work, task by task, edge and error cases included, and which gates are the
evidence that a task is done.

## Changes

How an existing work product grows — add, modify, remove, rename — instead of
being rewritten.

## Done

The stage's gates pass. Size budgets: <the limits>. Completeness wins over a
budget. Report the verified outcome, the open findings and assumptions, and the
next step.
```
