---
name: review_code_skill
description: "Rules for reviewing a pull request (SUP.1 BP1, SWE.3 BP5): a reviewer agent that is not the author approves the current head from its own declared account, in a session of its own, with the checklist complete — logging only for a change with code; a person approves every architecture pull request and 1 in N of the others; faults left unfixed become non-conformance issues."
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
- **A person** — every pull request that changes *paths.architecture_dir*, and
  every pull request whose number is a multiple of *review.sample_every*. This
  is seal 4: the person's approval on GitHub, never a file the agent writes.

Both approve the pull request's **current head**: a push after an approval
needs a new one.

## Inputs

- The pull request — its changed files, its commits and its description.
- The requirements, designs and decision records the changed files name with
  their markers.
- The CI run of the head — every gate passed, and the verification report.
- **qf.yaml** — *review.agents*, *review.sample_every*,
  *paths.architecture_dir*.

## Contract

The *review* section of *qf.v1*: *agents* lists the host accounts the reviewer
agent posts from; an approver that is none of them, no bot and not the author
counts as a person. *sample_every* is the N of *1 in N*. The review's body
carries the checklist, as *post_review_tool* writes it; *logging* is left out
when the pull request changes no file under *paths.code_dir*:

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
| R4 | A person approves the current head of every pull request that changes the architecture or the gates' own files (the CI file, the framework pin, qf.yaml), and of every one whose number is a multiple of N | verify_delivery_reviewed_gate · MISSING_PERSON_APPROVAL |
| R5 | A merged pull request's final head passed the gates check; while a release is proposed, every commit since the last release meets R1–R4 and this rule | verify_delivery_reviewed_gate · GATES_NOT_PASSED |
| R6 | **Correctness** — the change does what its requirements, design and decision records say, error cases included | Checkpoint 4 |
| R7 | **Style** — names follow the glossary and the conventions of the stack and of the framework's forms; no dead code, no commented-out code, no text left over | Checkpoint 4 |
| R8 | **Traceability** — every marker names the requirement, unit, component or flow the file really serves, not just one that exists | Checkpoint 4 |
| R9 | **Logging** — the events the observability requirements list are emitted where the sequence diagrams say | Checkpoint 4 |
| R10 | A finding is fixed in the same pull request, or recorded as an issue labelled *non-conformance* that links the pull request; a remark fixed before merge stays in the review | Checkpoint 4 |

## Not checkable

- The quality of the review itself — that is what the person's sample is for.
- That the reviewer agent's token stays in the reviewer's own session — left to
  the person who starts it; the person's sample shows a review that was not
  given.

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
  sample_every: 5
urgent_approvers: [lead-bob]
change_approvers: [lead-bob]
escalate_after_days: 30
```
