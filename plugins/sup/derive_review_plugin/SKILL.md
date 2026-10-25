---
name: derive_review_plugin
description: "Reviews one pull request as the reviewer agent: in a session of its own, from its own declared account, never the author's, after every gate passes; checks what no gate can — correctness, style, traceability, and logging for a change with code — and posts its decision with the checklist and the review record (whether a person is needed, every finding's outcome, the changed designs told as stories, and with the results the tests described from the test alone); findings left unfixed become non-conformance issues."
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
person's approval (seal 4: the results, or a question of what is wanted), deciding
that a person is not needed (the files decide that; you can only add a
request).

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
   that wait for a review. Read the head's crossing sign, the commit status
   *qf/merge*
   (*gh api repos/<owner>/<repo>/commits/<head>/status*): *Wait: the
   reviewer agent's approval*, alone or with *a review by …* (a person's
review), means
   everything else is green; *Wait: gates running* means
   wait; any *gates red* means stop and report it. Without the sign (a CI
   file older than v2.1.0), read the head's gates run
   (*gh api "repos/<owner>/<repo>/actions/runs?head_sha=<head>"*). A 403
   means the token cannot read CI: stop and send the person to
   *QUICKSTART.md* step 3, item 5.
2. **Read** — every changed file, with what its markers name.
3. **Judge** — the checklist items of *review_code_skill* the pull request
   asks for: correctness, style, traceability, and logging when it changes
   code. Each finding names the file, the line and what must change.
4. **Decide** — approve only when every item holds; otherwise request
   changes.
5. **Ask for a person, or not** — only for one of five conditions no file
   shows, with its reason in one line: 1 the rating looks too low (the change
   handles passwords, personal data, payments, permissions or deleting data,
   and its requirements are rated medium or low, or none covers it); 2 the
   meaning is unclear (a requirement reads two ways, and the code chose one);
   3 beyond what was approved; 4 cannot be undone (it deletes, rewrites or
   migrates stored data, or publishes, sends or pays); 5 cannot be verified
   (an outside service is only simulated, timing), or the same finding came
   back after three rounds. Never for size, style or taste. A *no* cancels
   nothing the files call for.
6. **Record** — the review record (*review.v1*): your answer to step 5;
   every finding of every round with its outcome (*fixed*, *withdrawn*, or
   *disputed* with the author's answer and your final position); and, when
   *classify_pull_request_tool* says a person reviews the pull request, what
   it does in one plain sentence (*summary*); its changed designs told as
   stories in a fresh session that sees the designs only
   (*agent/describe_design_prompt.md*); and, when it brings the results, its
   software-level tests described in a fresh session that sees the tests
   only (*agent/describe_tests_prompt.md*) — never by you, who read the
   requirements. A story step marked as a gap that a requirement answers is
   a finding; a gap no requirement answers goes to the person as a question
   of what is wanted.
7. **Post** — from your own account, in your own session
   (*agent/run_reviewer_agent.md*; its token in *QF_HOST_TOKEN* there only):
   *python tools/post_review_tool.py --pull-request N --decision approve
   --record FILE* (or *request_changes*, with *--failing* and *--findings
   FILE*). The tool writes the items the pull request asks for in their fixed
   form, and the record as a *```yaml review* block.
8. **Follow up** — a finding the author fixes in the pull request needs
   nothing more; one the architect defers becomes an issue labelled
   *non-conformance* whose *nonconformance* block names the pull request
   (*found_in*; *track_nonconformances_skill*).

After each push to the pull request, review the new head: an approval covers
only the head it was given on.

## Changes

A review is never edited: after a push, post a new review of the new head. A
finding fixed since the last review is not repeated; one still open is.

## Done

*verify_delivery_reviewed_gate* finds your approval of the current head with the
checklist complete and the record valid, every changed design told and, with
the results, every test described; on a pull request that brings the results
or asks a question of what is wanted, it then waits for the person.

Size budgets: at most 3 questions per round; one finding per problem.
Completeness wins over a budget: never leave a changed file unread or a
finding unsaid to stay within one.

Report: the decision, the findings with file and line, the questions still
open, and whether the pull request waits for a person (seal 4) and why.
