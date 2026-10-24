---
name: report_framework_feedback_skill
description: "Rules for the framework feedback log (principle #47): every framework weakness found while building recorded as a complete entry, never worked around silently, and every framework version bump accounted for with findings or a no-findings line."
---

# skill: report_framework_feedback_skill

**Stage:** 9 · SUP.1 Quality assurance — applies at every stage, checked at the delivery
**Loaded with:** review_pull_request_plugin
**Contract:** contracts/qf_contract.v1.schema.json
**Gates:** check_framework_feedback_gate
**Replaces:** framework-feedback (main)

## What it governs

The product's framework feedback log, *qf.yaml paths.framework_feedback_file*,
copied from the framework's *templates/FRAMEWORK_FEEDBACK.md*. The framework's
defects are invisible to the framework: a gate that passes without checking
leaves no red build behind. The log makes such a finding survive the session
that found it, so it is fixed upstream for every product, not patched around in
one.

Write an entry when a gate passes on input it did not read or fails on correct
input, when a declared rule has no gate behind it, when a framework document
says something untrue, when the product had to work around the framework, or
when a framework version bump changed behaviour.

## Inputs

- The framework behaviour observed, and the command and output that show it.
- The framework version: the submodule commit at *paths.framework_dir* and its
  release tag.
- The existing log, for the next *FB-&lt;n&gt;* and to avoid a duplicate.

## Contract

*qf.v1 paths.framework_feedback_file* and *paths.framework_dir*. Under the
log's *## Log* heading, every *### FB-&lt;n&gt;* entry has the fields of the
template: Date, Framework version, Severity (critical, high, medium, low),
Class (C1–C6), Status, and the sections What the framework claims, What
actually happens, Reproduction, Verification, Blast radius, Impact on this
product and Workaround applied.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every entry has every field of the template, a known severity and class, and no placeholder text left | check_framework_feedback_gate · INCOMPLETE_FEEDBACK_ENTRY |
| R2 | A pull request that moves the framework submodule names the new version in the log, in the team's own words: an entry's **Framework version** or a line starting *No findings for*; the framework's quoted answers and other prose do not count | check_framework_feedback_gate · UNACCOUNTED_FRAMEWORK_BUMP |
| R3 | A framework weakness is recorded before the work moves on, and never fixed inside the framework's folder or worked around without an entry naming the files | Checkpoint 4 |
| R4 | A finding states whether it was run or only read | Checkpoint 4 |

## Not checkable

- That a weakness was noticed at all — no script can decide that, and a gate
  that asked for findings would invite invented ones. An empty log passes.

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
