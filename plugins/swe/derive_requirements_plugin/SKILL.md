---
name: derive_requirements_plugin
description: "Works out the requirements of a feature from its approved diagrams and the customer's wishes — explore, ask, derive element by element with edge and error cases, grow existing requirements instead of rewriting them."
---

# plugin: derive_requirements_plugin

**Stage:** 2 · SWE.1 Software requirements
**Fills slot:** create_requirements_plugin
**Loaded with:** write_requirements_skill, define_glossary_terms_skill, specify_nfr_measurement_skill

## Goal

From the approved diagrams, their invariants and the customer's wishes to the
requirements of the feature and the glossary terms they use.

A requirement states behaviour someone can observe, not how it is built: if the
implementation could change without changing what the user or a neighbouring
system sees, it does not belong in a requirement.

Not this method's job: the form of a requirement (the rules skills loaded with
it), the checks (the stage's gates), the approval (the architect, at checkpoint 2).

## Explore

Read before writing anything:

- the approved diagrams — every node, edge, message and invariant;
- the wishes, for constraints the diagrams cannot show (a runtime, a database);
- the glossary, so existing terms are reused, not reinvented;
- the existing requirements, if any — they are the source of truth to grow;
- the findings of the previous attempt, on a retry.

List the diagram elements no requirement covers yet: that list is the work.

## Ask

Before writing, settle what the inputs do not say. Ask the round in one message:
3–5 questions, the ones whose answer would change a requirement, each with the
assumption you will write from if it is skipped — so the person can answer,
correct or skip any of them:

- business rules — limits, permissions, what happens after how many attempts;
- thresholds — how fast, how many, how available, and how it is measured;
- error behaviour — what the user sees when something fails;
- criticality — what it costs if this requirement is not met;
- operating environment — what it touches outside the software;
- scope — what belongs to this feature and what explicitly does not;
- new domain terms and their meaning.

Then write from the answers and the accepted assumptions, and keep the
assumptions in the feature document and the report. Offer a second round only
for what the answers opened up. Never invent an answer — a threshold, a rule or
a term nobody gave you is an open question or a stated assumption, not a fact.

## Depth

- **Lite** — a feature whose failure is an inconvenience: every requirement gets
  its happy case and at least one error case.
- **Full** — security, personal data, money, criticality high, or a feature other
  features depend on: every edge and error case you can name, the non-functional
  requirements with thresholds, and the operating-environment impact in detail.

When in doubt, full.

## Steps

One task per diagram element, in this order:

1. **System level** — for each node, edge and invariant of the architecture
   diagrams, the system-level requirement(s) it implies.
2. **Software level** — for each participant and invariant of the feature's
   sequence diagram, the software-level requirement(s), each refining the
   system-level requirement it serves.
3. **Acceptance criteria** — from each message of the sequence diagram: the
   happy case, then the edge cases (boundaries, empty or unusual input), then
   the error cases (a failure and how it is handled).
4. **Non-functional and observability** — a requirement for every threshold,
   with the suite that measures it; one observability requirement per feature,
   with the events it logs and what watches them.
5. **Constraints** — from the wishes, deriving from the wish. Only a constraint
   (a runtime, a database, a standard to follow) derives from a wish directly. A
   wish about behaviour — security, speed, what the user sees — enters through
   the diagram: derive from the invariant or element that carries it. A
   behaviour wish the diagram does not carry is a finding for the architect, not
   a reason to bypass the diagram.
6. **Terms** — every domain term marked *_term_* and defined once in the
   glossary, including the ones you introduce yourself: no gate can tell a new
   domain term from an ordinary word, so this step is the only check before
   checkpoint 2.

Throughout: **one behaviour per requirement**. A statement that joins two
behaviours ("locks the account and unlocks it after 15 minutes") is two
requirements, each with its own criteria and tests.

After each batch, run the stage's gates: the uncovered elements and the other
findings are what is still to do, and a task is done only when its findings are
gone. Never mark a task done on your own judgement.

## Changes

When requirements already exist, grow them; never rewrite the file:

- **Added** — a new requirement with the next free UID.
- **Modified** — edit the whole requirement, every criterion kept unless it is
  wrong; note what it said before in the change summary.
- **Removed** — delete it, with the reason and what replaces it.
- **Renamed** — a changed statement or term, with what must follow it.

A UID is never reused. Give the architect a change summary listing each added,
modified, removed and renamed requirement.

## Done

The stage's gates pass: check_requirements_contract_gate,
verify_requirements_to_diagram_link_gate and check_glossary_gate.

Size budgets: a statement is one sentence; a criterion at most 3 lines; at most
5 questions per round; a change summary at most 300 words. Completeness wins over
a budget: never leave out an element, a requirement or an edge case to stay
within one — say briefly why it is longer, and continue.

Report: the requirements by level and kind, the coverage of happy, edge and error
cases, the domain terms you introduced, the assumptions still open, and the next
step — the architect's review at checkpoint 2.
