---
name: derive_validation_scenarios_plugin
description: "Works out, from the customer's wishes only, a validation scenario for every wish — an automated acceptance test through the product's outside interfaces, or the written steps of a guided demo or a trial use — and the validation section of the verification plan; never reads the requirements or the code."
---

# plugin: derive_validation_scenarios_plugin

**Stage:** 11 · VAL.1 Validation
**Fills slot:** create_validation_scenarios_plugin
**Loaded with:** validate_release_skill

## Goal

From the wishes to the scenarios the customer will run: for every wish, at
least one scenario that shows, in the customer's own terms, that the product
serves the intended use — *a 1-tonne cart crosses on market day*, not *the
load endpoint returns 200*. Also, the first time, the validation section of
the verification plan.

You are the village's crew. You know what the village asked for, never how
the bridge was specified or built: you do not read the requirements, the
design, the code or the tests of stages 5 to 8. A scenario that only repeats
a requirement's test checks the product was built right a second time, and
never whether it is the right thing.

Not this method's job: the deployment to staging (the product's own
pipeline), running the scenarios and the validation record (the agent, with
*write_validation_record_tool*, and the person who runs a guided demo), the
decision (the customer, checkpoint 5), the form (the rules skill loaded with
it), the checks (the stage's gates).

## Explore

Read before writing anything:

- every wish — its statement, its source and its kind;
- the approved diagrams and their wishes links — what the customer sees
  happen, in which order;
- the architecture's outside interfaces — where a scenario reaches the
  product (a page, an API, a file drop), never a component inside it;
- the tech stack — the *validation* suite, its *results* path, and
  *validation_test_files*;
- the verification plan's validation section and the existing scenarios
  under *paths.validation_scenarios_dir* — the source of truth to grow.

Never open *paths.requirements_dir*, the design, *paths.code_dir* or a test
folder of stages 5 to 8.

## Ask

Ask the round in one message: 3–5 questions whose answer would change a
scenario or its environment, each with the assumption you will write from if
it is skipped:

- what "it works" looks like to the person who asked for each wish — the
  observation that would convince them;
- which wishes need a person to judge them (a guided demo or a trial use)
  rather than an automated check;
- what the staging environment holds — realistic data, the same outside
  systems, a replayed load;
- who runs a guided demo, and who in the customer's organisation decides.

Never invent a customer's criterion: a criterion nobody gave you is an
assumption, stated as one.

## Depth

- **Lite** — wishes the customer can check by looking at one outcome: one
  automated scenario per wish.
- **Full** — wishes about a whole working day, a load, a person's judgement
  or an outside system: also a guided demo or a trial use for them, and the
  awkward cases the customer named (a full cart, a closed lane, a rainy day).

When in doubt, full.

## Steps

1. **Plan** — the first time, the validation section of the verification
   plan: the selection (every automated scenario at every release, and which
   scenarios run by hand), the regression rule, and per scenario, in the order
   they run, its technique, pass/fail criteria in the customer's terms, entry
   criteria and environment.
2. **Automated scenarios** — per wish the product can show without a person's
   judgement, an acceptance test through the outside interfaces, marked
   *@wish[W-&lt;n&gt;]*, in a file matching *validation_test_files* under
   *paths.validation_scenarios_dir*. It reaches the product at the address the
   deployment gives (an environment variable of the product's choosing),
   never by importing its code.
3. **Written scenarios** — per wish a person must judge, a Markdown file under
   the same folder marked *@wish[W-&lt;n&gt;]*: who runs it, the steps in the
   customer's words, and what they should see.
4. **List** — every scenario in the plan's validation section; none listed
   that does not exist.
5. **Commit** — the scenarios and the plan, in one commit of the delivery's
   pull request, before any release: scenarios written on a release pull
   request would change the configuration items after its record.

After each commit, run the stage's gates: the stage is done only when their
findings are gone.

## Changes

When scenarios already exist, grow them; never rewrite them:

- a new wish gets its scenario in the delivery that realises it;
- a changed wish changes its scenarios and their plan entries;
- a retired wish's scenarios and entries are removed with it.

## Done

The stage's gates pass: verify_acceptance_to_wishes_link_gate,
check_verification_plan_gate; for a release, verify_release_evidence_gate
too, once the agent has recorded the results and the customer has decided.

Size budgets: one wish per scenario file; at most 5 questions per round.
Completeness wins over a budget: never leave out a wish, an awkward case the
customer named, or a plan entry to stay within one.

Report: per wish its scenarios and technique, which ones a person must run,
the assumptions still open, and the next step — the delivery's review, or,
for a release, the deployment to staging.
