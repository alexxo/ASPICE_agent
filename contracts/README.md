# contracts

The shared interface of the ASPICE Agent (WP0). The plugin writes to these
contracts, the framework skills describe them, the gates check them, and the
agent's scripts read them. Each contract is one JSON Schema (draft 2020-12),
versioned in its name, with valid and invalid examples under `examples/<name>/`.

| Contract | What it describes | Stored as | Read by |
|---|---|---|---|
| `requirement.v1` | One requirement (SWE.1 BP1–BP4) | A fenced `yaml requirement` block in a Markdown file under `paths.requirements_dir` | check_requirements_contract_gate, verify_requirements_to_diagram_link_gate |
| `wish.v1` | One customer wish, of kind behaviour or constraint | A fenced `yaml wish` block in `paths.wishes_file` | verify_diagram_to_wishes_link_gate, verify_requirements_to_diagram_link_gate |
| `glossary_term.v1` | One glossary entry | A fenced `yaml glossary_term` block in `paths.glossary_file` | check_glossary_gate |
| `diagram.v1` | The elements of one diagram | JSON, produced by the framework's diagram adapter from the diagram source (Archify JSON) and its invariants file | verify_requirements_to_diagram_link_gate |
| `diagram_wishes.v1` | Which wishes each element of one diagram realises | `<diagram>.wishes.yaml` next to the diagram, approved with it at checkpoint 1 | verify_diagram_to_wishes_link_gate |
| `invariants.v1` | The behavioural invariants of one diagram | `<diagram>.invariants.yaml` next to the diagram | Diagram adapter, check_diagram_contract_gate |
| `qf.v1` | The framework configuration: paths (the framework submodule, the CI file, the framework feedback log and the release records included), slot table, who reviews a pull request (reviewer accounts, the people called in), the product's own configuration items | `qf.yaml` at the product root | Config reader (pipeline preconditions), check_config_items_gate |
| `environment.v1` | Where this machine keeps the plugins the slots name | `.qf/environment.yaml` in the product or `~/.config/quality-framework/environment.yaml`, never committed | Agent config reader |
| `stack.v2` | The product's tech stack: one row per tool the product takes from outside, in its area (language, libraries, llm, test runner, lint, the scanners, the areas the framework gives…), with its exact version, or the area marked not needed with the reason; the version command of every tool the framework runs, the command of every check and scanner (scanners with their SARIF results); the code-file patterns, the environment read patterns and the decision record | A YAML work product of SWE.2, approved at checkpoint 3 | check_stack_decision_gate, check_stack_commands_gate, scan_security_gate, write_stack_table_tool, every plugin |
| `component.v1` | One software component of the architecture (SWE.2 BP1, BP3, BP4): the node it comes from, budget, size, the requirements it meets | A fenced `yaml component` block in a Markdown file under `paths.architecture_dir` | check_design_contract_gate |
| `interface.v1` | One interface between components (SWE.2 BP1); an external one names its security test templates (principle #16) | A fenced `yaml interface` block next to the components | check_design_contract_gate, verify_security_tests_gate |
| `decision.v1` | One architectural decision record (SWE.2 BP3) | A fenced `yaml decision` block in `paths.decisions_dir/NNNN-<slug>.md` | verify_decision_records_gate, check_design_contract_gate |
| `unit.v1` | One software unit of a component's detailed design (SWE.3 BP1): inputs and outputs with type, range and unit of measure | A fenced `yaml unit` block in `<component-id>.md` under `paths.detailed_design_dir` | check_detailed_design_contract_gate, verify_code_to_design_link_gate |
| `verification_plan.v1` | The product's verification plan (SWE.4 BP1, BP2; SWE.5 BP1, BP3): techniques, criteria, infrastructure, selection, regression, minimum coverage and time budget for units; the integration order with its steps, preconditions and selections for components and flows; the software level's criteria, environment and order of suites (SWE.6 BP1, BP2); the validation scenarios with their technique, criteria and environment, the selection and the regression (VAL.1 BP1, BP2); in each section the commands of its suites — the test runner, where each writes results (JUnit XML), the unit suite coverage (Cobertura XML) and a measuring suite its measurements (measurements.v1), the test-file patterns, and the command that runs only given tests (run_selected, selected_form) | One fenced `yaml verification_plan` block in `paths.verification_plan_file` | check_verification_plan_gate, check_stack_commands_gate, verify_tests_to_components_link_gate, write_validation_record_tool, select_tests_tool, every gate that runs a suite |
| `measurements.v1` | The values a suite measured for non-functional requirements (SWE.6 BP3): requirement, value, unit | JSON written by the suite to its plan entry's `measurements` path, kept with the run | verify_nfr_thresholds_gate, write_verification_report_tool |
| `release.v1` | One release (SUP.8 BP5–BP7): version, configuration items changed since the previous release, framework version | `<version>.yaml` under `paths.releases_dir`, added by the release pull request and tagged `v<version>` after its merge | verify_baseline_gate, write_release_tool |
| `validation.v1` | One validation record (VAL.1 BP3, BP4): the environment, the deployed commit, and every scenario's technique and result | `<version>.yaml` under `paths.validation_records_dir`, added by the release pull request after the deployment to staging | verify_release_evidence_gate, verify_acceptance_to_wishes_link_gate, write_validation_record_tool |
| `problem.v1` | One problem (SUP.9 BP1, BP2, BP4, BP5): what, where, how to reproduce, expected and actual, status; then cause, impact, severity, affected parties, notification, change request | A fenced `yaml problem` block in the body of a host issue labelled *problem*; its tests name it `@problem[<n>]` | check_problem_record_gate, check_urgent_fix_gate, verify_problem_closure_gate, report_problem_trends_gate |
| `review.v1` | What the reviewer agent hands to the person's review (SUP.1 BP1): whether it asks for a person (one of five conditions), each finding's outcome, what the pull request does, each test described from the test alone, each changed design told as stories from the design alone, and which story shows each asked requirement | A fenced `yaml review` block in the reviewer agent's review, written by post_review_tool --record | verify_delivery_reviewed_gate, classify_pull_request_tool, post_checkpoint_review_tool |
| `nonconformance.v1` | One fault left unfixed (SUP.1 BP6): the pull request it was found in and the one that fixed it | A fenced `yaml nonconformance` block in the body of a host issue labelled *non-conformance* | check_nonconformances_gate, check_escalations_gate, report_quality_trends_gate |
| `retro_action.v1` | One retrospective action item (principle #41): owner and due date | A fenced `yaml retro_action` block in the body of a host issue labelled *retro-action* | check_retro_actions_gate |
| `change_request.v1` | One change request (SUP.10 BP1, BP2, BP4): what, initiator, reason, status; then the affected wishes, diagram elements and requirements, dependencies, size, the problem that caused it | A fenced `yaml change_request` block in the body of a host issue labelled *change-request*; its commits name it `#<n>` | check_change_record_gate, verify_change_approval_gate, verify_change_trace_gate, verify_change_closure_gate |
| `env_variable.v1` | One environment variable the code reads (principle #23): description, required, example, valid values | A fenced `yaml env_variable` block in `paths.env_variables_file`, written with the detailed design | check_detailed_design_contract_gate, check_env_config_gate |
| `approval.v1` | One human decision at a checkpoint | One YAML file under `paths.approvals_dir` | verify_diagram_approval_gate, verify_requirements_approval_gate, checkpoint recorder |
| `stage_done.v1` | The record that a stage without a closing checkpoint was finished once: its gates passed (§ 5 *What CI fails on*) | One YAML file `<date>-stage-<n>-done.yaml` under `paths.approvals_dir`, written by the agent | resolve_stage_tool, record_stage_done_tool |
| `findings.v1` | A gate's result | JSON on the gate's stdout | Gate runner, retry policy |

## Rules

- **The schema checks one record.** Rules across records — a unique UID, a
  Refines target that exists, no cycle, every diagram element covered — are gate
  rules, not schema rules.
- **YAML is read as JSON.** Timestamps are not converted to dates; every value
  is checked as the JSON value it would be.
- **A diagram element is referenced as `<diagram>#<id>`** (e.g.
  `login#INV-1`). The diagram ID is the source file name up to its first dot.
  Node, edge and message IDs are the IDs in the diagram source (Archify
  components, participants, connections, messages); invariant IDs are the
  `INV-<n>` entries of the invariants file.
- **The framework owns the diagram adapters**, one per diagram tool, Archify
  first. A plugin never ships its own.
- **Requirements name suites, the plan names commands, the stack names tools.**
  The suite vocabulary (unit, integration, software, bench, security, e2e) is
  the same in `requirement.v1` and in the sections of `verification_plan.v1`;
  a test keeps it so. The plan also has the *validation* suite, which runs the
  validation scenarios against a deployed release and which no requirement
  names. Each suite runs with a test runner of `stack.v2`, which pins its
  version.
- **An approval is bound to content.** It lists the SHA-256 of every file it
  covers; a changed file no longer matches its approval.

## Tests

`tests/schema/test_contracts.py` validates every valid example and
requires every invalid example to fail at the JSON path and keyword its
`invalid/expect.yaml` names.
