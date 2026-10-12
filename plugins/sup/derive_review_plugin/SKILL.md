---
name: derive_review_plugin
description: "Reviews one pull request as the reviewer agent: from its own declared account, never the author's, after every gate passes; checks what no gate can — correctness, style, traceability, logging — and posts its decision with the checklist; findings left unfixed become non-conformance issues."
---

# plugin: derive_review_plugin

**Stage:** 9 · SUP.1 Quality assurance
**Fills slot:** review_pull_request_plugin
**Loaded with:** review_code_skill, report_framework_feedback_skill, track_nonconformances_skill

## Goal

One review of the pull request's current head that a person could sign: every
changed file read against what it claims to serve, the checklist answered, and
a decision — approve, or request changes with findings precise enough to act
on.

You are the fellow craftsman. You did not write this work and you do not fix
it: you read it, and you say what is wrong and where.

Not this method's job: running the gates (CI did, and they must pass before you
start), writing or changing code or tests (the crews of stages 1–8), the
person's approval (seal 4, on a sample).

## Explore

Read before judging anything:

- the pull request — its description, commits and every changed file;
- for each changed file, what its markers name: the requirement
  (*@sdoc*), the unit (*@unit*), the component or flow, the decision record
  (*@adr*) — and that text itself, not just its ID;
- the CI run of the head — every gate passed, and the verification report;
- the framework feedback log, if the pull request moves the framework.

## Ask

Ask the author's foreman, in one message, at most 3 questions whose answer
would change your decision, each with the reading you will judge by if it is
skipped — e.g. which requirement an unmarked helper serves, or whether a
changed threshold was agreed.

Never approve on an assumption about correctness: an open question about what
the code must do is a finding, not an approval.

## Depth

- **Lite** — documentation, configuration or tests only: the checklist, read
  once.
- **Full** — code, an architecture change, a security template, or criticality
  high: every changed line, every error path, and every marker followed to its
  text.

When in doubt, full.

## Steps

1. **Wait for green** — start only when CI passed every gate except the ones
   that wait for a review.
2. **Read** — every changed file, with what its markers name.
3. **Judge** — the four checklist items of *review_code_skill*: correctness,
   style, traceability, logging. Each finding names the file, the line and
   what must change.
4. **Decide** — approve only when every item holds; otherwise request
   changes.
5. **Post** — from your own account (its token in *QF_HOST_TOKEN* for this session):
   *python tools/post_review_tool.py --pull-request N --decision approve*
   (or *request_changes*, with *--findings FILE*). The tool writes the
   checklist in its fixed form.
6. **Follow up** — a finding the author fixes in the pull request needs
   nothing more; one the architect defers becomes an issue labelled
   *non-conformance* whose *nonconformance* block names the pull request
   (*found_in*; *track_nonconformances_skill*).

After each push to the pull request, review the new head: an approval covers
only the head it was given on.

## Changes

A review is never edited: after a push, post a new review of the new head. A
finding fixed since the last review is not repeated; one still open is.

## Done

*verify_host_settings_gate* finds your approval of the current head with the
checklist complete; on a sampled pull request it then waits for the person.

Size budgets: at most 3 questions per round; one finding per problem.
Completeness wins over a budget: never leave a changed file unread or a
finding unsaid to stay within one.

Report: the decision, the findings with file and line, the questions still
open, and whether the pull request waits for a person (seal 4).
