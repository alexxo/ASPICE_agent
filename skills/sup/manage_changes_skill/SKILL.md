---
name: manage_changes_skill
description: "Rules for change request management (SUP.10): every change a change-request issue with a complete record, analysed before it is approved, signed by an approver before the first commit that builds it, traced to what it touches and to the problem that caused it, and closed only once it is on the main branch and its initiator confirms it."
---

# skill: manage_changes_skill

**Stage:** 13 · SUP.10 Change request management — triggered by a changed wish, its rules checked on every pull request once the flow is done
**Loaded with:** the ASPICE Agent itself; stage 13 has no plugin
**Contract:** contracts/change_request_contract.v1.schema.json
**Gates:** check_change_record_gate, verify_change_approval_gate, verify_change_trace_gate, verify_change_closure_gate

## What it governs

What happens when the customer asks for something different from what was
agreed — a new or amended wish, diagram or requirement — from the request to
the initiator's confirmation. A defect is not a change: when the product does
not do what was agreed, that is a problem (*resolve_problems_skill*).

## Inputs

- **The change requests** on the code host, labelled *change-request*; the
  issue's number is the change's ID.
- **qf.yaml** — *change_approvers*, who may approve a change.
- **The commits** — a commit that names *#n* builds change request *n*.
- **The wishes, the diagrams and the requirements** — what a change may
  touch.

## Contract

A change request is an issue labelled *change-request* whose body holds one
fenced block:

    ```yaml change_request
    what: …          # one line
    initiator: …     # a role or a person
    reason: …
    status: requested  # requested | analysed | approved | implemented | closed
    ```

Analyse it before it is approved: *affected* — the *wishes* (W-n), diagram
*elements* (diagram#element) and *requirements* (REQ-n) it changes — the
change requests it *depends_on*, its *size* (S, M, L or XL) and, when a
problem caused it, that *problem*'s number (the problem names it back in its
*change_request*).

A person in *change_approvers* comments */approve-change* on the issue before
anyone builds it; the agent asks with a choice commented on the issue
(*agent/ask_person_tool.py --markdown*), each option naming its command. The change then enters the flow at stage 1 as a new or
amended wish, and every commit that builds it names *#n*. Once its last commit
is on the main branch, set the status to implemented; the initiator comments
*/confirm-change*, and the issue is closed.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every change request has its block, following change_request.v1 — at release every one, on every pull request every one its commits name | check_change_record_gate · INCOMPLETE_CHANGE_RECORD |
| R2 | A change request past the requested status, or named by a commit, states its affected items and size | check_change_record_gate · MISSING_CHANGE_ANALYSIS |
| R3 | Every dependency is a change request | check_change_record_gate · UNKNOWN_DEPENDENCY |
| R4 | A change request a commit names has /approve-change from a person in change_approvers, given before the first commit that names it | verify_change_approval_gate · UNAPPROVED_CHANGE |
| R5 | Every affected wish, diagram element and requirement exists | verify_change_trace_gate · UNKNOWN_AFFECTED_ITEM |
| R6 | A change request and the problem that caused it name each other | verify_change_trace_gate · UNLINKED_PROBLEM |
| R7 | At release, a closed change request has a commit that names it on the main branch | verify_change_closure_gate · CLOSED_WITHOUT_IMPLEMENTATION |
| R8 | At release, a closed change request has /confirm-change from its initiator, given after its last commit reached the main branch | verify_change_closure_gate · MISSING_CHANGE_CONFIRMATION |
| R9 | While a release is proposed, the report lists the change requests the release implements and those still open | verify_change_closure_gate · MISSING_CHANGE_SECTION |
| R10 | The analysis is right: the affected items are all of them, and the size is honest | Review |

## Not checkable

- That a commit naming *#n* really builds the change, rather than mentioning
  it — the reviewer reads every commit.
- That the approver weighed the change — the signature is theirs.

## Example

```yaml change_request
what: Lock an account after ten failed sign-ins, not five.
initiator: product owner
reason: Support handles too many lockouts of people who mistyped.
status: analysed
affected:
  wishes: [W-02]
  elements: [login#INV-1]
  requirements: [REQ-0047]
depends_on: []
size: S
problem: 12
```
