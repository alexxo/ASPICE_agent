---
name: review_code_skill
description: "Rules for reviewing a pull request (SUP.1 BP1, SWE.3 BP5): a reviewer agent that is not the author approves the current head from its own declared account, in a session of its own, with the checklist complete — logging only for a change with code — and its review record; a person approves the results of software verification (checkpoint 4) and answers the questions of what is wanted, in CI's review in plain words, never a review of the build; faults left unfixed become non-conformance issues."
---

# skill: review_code_skill

**Stage:** 9 · SUP.1 Quality assurance
**Loaded with:** review_pull_request_plugin
**Contract:** contracts/qf_contract.v1.schema.json
**Gates:** verify_delivery_reviewed_gate
**Replaces:** code-review-gate (main)

## What it governs

The review of one pull request, after the gates of every stage the product has
reached pass in CI. The gates check every rule a script can check; the review
checks what they cannot: whether the change is right, readable, traced to the
right requirement and observable. Two reviewers, in this order:

- **The reviewer agent** — every pull request, at every stage. It is never the
  author: it runs in a session of its own (*agent/run_reviewer_agent.md*), the
  only one that holds its token, and posts from its own account, one of
  *qf.yaml review.agents*, with *tools/post_review_tool.py*, which writes the
  checklist in a fixed form. The token is a narrow one: for the product's
  repository only, able to review and not to push.
- **A person** — where they can judge, never the build itself
  (*classify_pull_request_tool*): the pull request that brings the results of
  software verification, stage 8 (checkpoint 4: each high-criticality and
  security requirement it proves, and every one that did not pass, achieved
  or not); a question of what is wanted on any pull request — a gap of a
  design's story that no requirement answers, a weakened test, a finding
  closed without a change, the reviewer agent's request; a change of the
  product's settings (*qf.yaml*, *.gitmodules*); and every architecture pull
  request. Never by number. CI posts the review in plain words as a comment
  mentioning *review.people*; the person ticks one box per question, then
  approves. This is seal 4: the person's approval on GitHub, never a file the
  agent writes.

Both approve the pull request's **current head**: a push after an approval
needs a new one.

## Inputs

- The pull request — its changed files, its commits and its description.
- The requirements, designs and decision records the changed files name with
  their markers.
- The CI run of the head — every gate passed, and the verification report.
- **qf.yaml** — *review.agents*, *review.people*,
  *paths.architecture_dir*.
- The reviewer agent's review record (*review.v1*).

## Contract

The *review* section of *qf.v1*: *agents* lists the host accounts the reviewer
agent posts from; an approver that is none of them, no bot and not the author
counts as a person. *people* are the accounts CI's review comment mentions.
The review's body carries the checklist, as *post_review_tool* writes it;
*logging* is left out when the pull request changes no file under
*paths.code_dir*; an approval also carries the review record (*review.v1*) as
a *```yaml review* block:

```
<!-- qf-review-checklist -->
- [x] correctness
- [x] style
- [x] traceability
- [x] logging
```

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every delivery is a pull request; every commit a push adds to the main branch came from a merged one | verify_delivery_reviewed_gate · NO_PULL_REQUEST, MERGED_WITHOUT_PULL_REQUEST |
| R2 | A declared reviewer agent, never the author, approves the current head | verify_delivery_reviewed_gate · MISSING_AGENT_REVIEW |
| R3 | The agent's approval carries the checklist with every item the pull request asks for checked: *logging* only when it changes a file under *paths.code_dir* | verify_delivery_reviewed_gate · INCOMPLETE_CHECKLIST |
| R4 | A person approves the current head of every pull request that brings the results of software verification (checkpoint 4), asks a question of what is wanted (a gap no requirement answers, a weakened test, a finding closed without a change, the reviewer agent's request), changes the product's settings (qf.yaml, .gitmodules), or changes the architecture | verify_delivery_reviewed_gate · MISSING_PERSON_APPROVAL |
| R5 | A merged pull request's final head passed the gates check; while a release is proposed, every commit since the last release meets R1–R4 and this rule | verify_delivery_reviewed_gate · GATES_NOT_PASSED |
| R6 | **Correctness** — the change does what its requirements, design and decision records say, error cases included | Review |
| R7 | **Style** — names follow the glossary and the conventions of the stack and of the framework's forms; no dead code, no commented-out code, no text left over | Review |
| R8 | **Traceability** — every marker names the requirement, unit, component or flow the file really serves, not just one that exists | Review |
| R9 | **Logging** — the events the observability requirements list are emitted where the sequence diagrams say | Review |
| R10 | A finding is fixed in the same pull request, or recorded as an issue labelled *non-conformance* that links the pull request; a remark fixed before merge stays in the review | Review |
| R11 | A change that reached the main branch without the delivery desk — a commit from no pull request, a pull request merged before its reviews or without a gates check that passed before the merge — blocks the release until a non-conformance names it and a person in *qf.yaml urgent_approvers*, not its author, comments */accept-delivery* on it; a re-run after the merge or a revert alone does not clear it | verify_delivery_reviewed_gate · MERGED_WITHOUT_PULL_REQUEST, GATES_NOT_PASSED |
| R12 | The agent's approval carries a valid review record: every changed design told as stories from the design alone; when a person reviews, what the pull request does; with the results, every software-level test the person reads described from the test alone | verify_delivery_reviewed_gate · INCOMPLETE_CHECKLIST |
| R13 | When the person's review has items, CI's review comment for the head has every item answered yes, and it did not change after the approval | verify_delivery_reviewed_gate · REVIEW_ITEMS_UNANSWERED, REVIEW_CHANGED_AFTER_APPROVAL |
| R14 | The agent asks for a person only for one of five conditions, with its reason; its *none* cancels no review the files call for | Review |
| R15 | Every story step names a source its design has: a message of its sequence diagram, a unit, or a decision its document names | verify_delivery_reviewed_gate · REVIEW_STORY_UNSOURCED |
| R16 | A story's gap that a requirement answers is a finding; the agent approves only gaps no requirement answers, and each goes to the person as a question of what is wanted, with what the build does there now, the lines that decide it and what follows for the user | verify_delivery_reviewed_gate · INCOMPLETE_CHECKLIST |
| R17 | With the results, the record lists the cases expected of each criterion of every requirement proved, from a session that saw the criteria alone (*agent/expect_cases_prompt.md*), copied unchanged, each with the test that checks it or *missing*; a missing case is a finding for the tester, and one held wrong is a question for a person (condition 2) | verify_delivery_reviewed_gate · REVIEW_EXPECTED_CASES_MISSING |

## Not checkable

- The quality of the review itself — the person's review checks it where it
  matters.
- That the test descriptions were written without the requirement when the
  reviewer agent is started by hand — the watcher writes them itself, in a
  folder holding only the tests.
- That the reviewer agent's token stays in the reviewer's own session — left to
  the person who starts it.

## Example

```yaml qf
contract: qf.v1
paths:
  requirements_dir: docs/requirements
  glossary_file: docs/glossary.md
  wishes_file: docs/wishes.md
  diagrams_dir: docs/diagrams
  approvals_dir: docs/approvals
  architecture_dir: docs/architecture
  decisions_dir: docs/decisions
  stack_file: docs/architecture/stack.yaml
  detailed_design_dir: docs/design
  code_dir: src
  verification_plan_file: docs/verification-plan.md
  env_variables_file: docs/configuration.md
  integration_tests_dir: it
  software_tests_dir: st
  observability_dir: observability
  framework_dir: .framework
  ci_file: .github/workflows/quality_gates.yml
  framework_feedback_file: FRAMEWORK_FEEDBACK.md
  releases_dir: releases
  validation_scenarios_dir: validation/scenarios
  validation_records_dir: validation/records
slots:
  create_diagram_plugin: archify
  create_requirements_plugin: quality-framework/derive_requirements_plugin
  create_architecture_plugin: quality-framework/derive_architecture_plugin
  create_detailed_design_plugin: quality-framework/derive_detailed_design_plugin
  create_unit_tests_plugin: quality-framework/derive_unit_tests_plugin
  create_unit_code_plugin: quality-framework/derive_unit_code_plugin
  create_integration_tests_plugin: quality-framework/derive_integration_tests_plugin
  create_software_tests_plugin: quality-framework/derive_software_tests_plugin
  review_pull_request_plugin: quality-framework/derive_review_plugin
  create_validation_scenarios_plugin: quality-framework/derive_validation_scenarios_plugin
review:
  agents: [qf-reviewer-bot]
  people: [lead-bob]
  architect: lead-bob
customer: Carla Village
urgent_approvers: [lead-bob]
change_approvers: [lead-bob]
escalate_after_days: 30
```
