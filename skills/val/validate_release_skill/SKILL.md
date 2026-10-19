---
name: validate_release_skill
description: "Rules for validation (VAL.1): every wish has a validation scenario listed in the plan, and a release is validated on a staging deployment of exactly what is released — every automated scenario and every affected wish with a result, none failed — then accepted by the customer before it is merged."
---

# skill: validate_release_skill

**Stage:** 11 · VAL.1 Validation — the scenario rules apply on every pull request, the rest while a release is proposed
**Loaded with:** create_validation_scenarios_plugin
**Contract:** contracts/validation_contract.v1.schema.json
**Gates:** verify_acceptance_to_wishes_link_gate, verify_release_evidence_gate, check_verification_plan_gate

## What it governs

Whether the product is the right thing: the customer's wishes checked by
validation scenarios in conditions close to the customer's, and the
customer's decision on each release. Verification (stages 5 to 8) asked
whether the product was built right; this rulebook asks whether it serves the
intended use.

The scenarios arrive with the deliveries, so a release pull request adds only
its records (decision 6 of the validation stage). A release is validated on
its pull request: after the release record (*record_baseline_skill*), the
product's own pipeline deploys it to staging, the scenarios run there, the
validation record is committed, and the customer accepts or rejects it
(checkpoint 5). The merge, and the tag after it, wait for the acceptance.

## Inputs

- **The wishes** (qf.yaml *paths.wishes_file*) — every wish needs a scenario.
- **The scenarios** under *paths.validation_scenarios_dir* — a file naming a
  wish with *@wish[W-&lt;n&gt;]*; an automated test when it matches the
  validation suite's *test_files*, written steps run by a person otherwise.
- **The verification plan's validation section** — every scenario with its
  technique, criteria, entry criteria and environment, the selection and the
  regression.
- **The proposed release** — a release record without a tag
  (*record_baseline_skill*); the configuration items it changes decide which
  wishes it affects.
- **The deployment** — which commit the product's pipeline deployed to
  staging. The framework never deploys.

## Contract

A validation record (validation.v1) is
*&lt;validation_records_dir&gt;/&lt;version&gt;.yaml*: *version* (the
release's), *environment* (*name*, e.g. staging, and the full SHA of the
deployed *commit*) and *results* — per scenario run, its repository path, the
*technique*, the *result* (pass or fail) and a *note* of what was seen. After
the deployment, run

    python .framework/tools/write_validation_record_tool.py --root . \
        --environment staging --commit <deployed sha>

It runs the *validation* suite, writes the automated results and keeps the
results already entered by hand; add the result of every guided demo or trial
use you ran, then commit the record. Ask the customer for their decision with
the report's validation section, and record it:

    python .framework/agent/record_checkpoint_tool.py --checkpoint 5 \
        --decision approved|changes-requested --approver <name> --role customer \
        [--comment <reason>] --root .

The decision covers the release record and the validation record by hash.

A release affects every wish when it changes what the customer gets — the
wishes, the diagrams, the requirements and glossary, the architecture and its
decisions, the stack, the detailed design, the code, the configuration
variables or the observability definitions — and no wish when it changes only
the framework pin, the tests, the plan, the approvals or the records
(decision 7).

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every wish has at least one scenario | verify_acceptance_to_wishes_link_gate · MISSING_SCENARIO |
| R2 | Every @wish marker names a wish that exists | verify_acceptance_to_wishes_link_gate · UNKNOWN_WISH |
| R3 | Once a scenario exists, the plan has a validation section that lists every scenario, and lists none that does not exist | check_verification_plan_gate · MISSING_VALIDATION_SECTION, UNSELECTED_SCENARIO, UNKNOWN_SCENARIO |
| R4 | A proposed release has a validation record that follows validation.v1 and is named after its version, and every release tag holds its own | verify_release_evidence_gate · MISSING_VALIDATION_RECORD |
| R5 | The deployed commit is in the release's history and holds its release record, and since it nothing changed but the validation record and the checkpoint 5 decision | verify_release_evidence_gate · WRONG_DEPLOYED_COMMIT |
| R6 | Every result names an existing scenario | verify_release_evidence_gate · UNKNOWN_SCENARIO |
| R7 | Every automated scenario has a result | verify_release_evidence_gate · MISSING_RESULT |
| R8 | No result is a failure | verify_release_evidence_gate · FAILED_SCENARIO |
| R9 | Every wish the release affects has a scenario with a result | verify_acceptance_to_wishes_link_gate · UNVALIDATED_WISH |
| R10 | The customer accepted the release, in the customer role, and the decision still matches both records | verify_release_evidence_gate · MISSING_CUSTOMER_DECISION, RELEASE_REJECTED |
| R11 | The scenarios reflect the customer's intended use, and the results satisfy them | Checkpoint 5 |

## Not checkable

- That the commit was really deployed, and that a result entered by hand was
  really observed — the customer's decision covers the record.
- Whether a scenario truly reflects the intended use, and whether the
  selection among the scenarios run by hand is good — the customer and the
  reviewer judge them.

## Example

```yaml validation
contract: validation.v1
version: 1.4.0
environment:
  name: staging
  commit: 3f2c9a1b7e4d5c6a8b9f0e1d2c3b4a5f6e7d8c9b
results:
  - scenario: validation/scenarios/test_loaded_cart_crosses.py
    technique: acceptance test
    result: pass
  - scenario: validation/scenarios/market-day-demo.md
    technique: guided demo
    result: pass
    note: Twelve carts crossed in an hour; the operator saw every crossing.
```
