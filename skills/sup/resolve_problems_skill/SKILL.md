---
name: resolve_problems_skill
description: "Rules for problem resolution (SUP.9): every defect a problem issue with a complete record, analysed before it is fixed — where it came in and where it got through — announced when it is bad, authorized when it is urgent, reproduced first by a failing test that names it, and closed only with that test on the main branch and the reporter's confirmation."
---

# skill: resolve_problems_skill

**Stage:** 12 · SUP.9 Problem resolution management — triggered by a defect, its rules checked on every pull request once the flow is done
**Loaded with:** create_unit_tests_plugin, then create_unit_code_plugin
**Contract:** contracts/problem_contract.v1.schema.json
**Gates:** check_problem_record_gate, check_urgent_fix_gate, verify_problem_closure_gate, report_problem_trends_gate

## What it governs

What happens to a crack (a defect) from the moment someone finds it to the
moment its finder says it is gone. A defect is not a change request: when the
product does what was agreed and the agreement is wrong, that is SUP.10.

## Inputs

- **The problem issues** on the code host, labelled *problem*; the issue's
  number is the problem's ID. Anyone who finds a defect, in operation too,
  opens one with the product's form, *.github/ISSUE_TEMPLATE/problem_report.yml*;
  no agent needs to run.
- **qf.yaml** — *urgent_approvers*, who may authorize a critical fix.
- **The tests** of every level, for the *@problem[&lt;n&gt;]* markers.
- **The main branch's history** — a problem is fixed there from the first
  commit that holds its test.
- **The framework feedback log**, for a problem that got through one of the
  framework's gates.

## Contract

A problem is an issue labelled *problem* whose body holds one fenced block:

    ```yaml problem
    what: …            # one line
    where: …           # as the reporter sees it
    reproduce: …       # steps and input
    expected: …
    actual: …
    status: open       # open | under-analysis | fixed | closed
    ```

A report from the form holds the reporter's answers instead: when you analyse
it, write the block from them, in the reporter's words, and keep the answers
below it.

Before it is fixed (status past open, or a test names it), add *cause*,
*impact* (*requirements* and *components*, by identifier), *severity* (low,
medium, high or critical), *origin* — the stage that brought the defect in —
and *escape* — the *stage* that should have caught it and *why* it did not,
both by their id in *agent/stages.yaml*. When the escape is the framework's
weakness — a gate that passed it, a rule the stage lacks — write a framework
feedback entry that names the problem, and file it once the person approved
it (report_framework_feedback_skill). A high or critical problem names its
*affected_parties* and the date they were *notified*. A problem whose fix
needs a change of requirements or design names its *change_request* (the issue
number), and the change desk carries it.

The fix comes test first: the tester writes a test of the level where the
crack shows, marked *@problem[&lt;n&gt;]*, in a test-only commit where it
fails; the coder fixes the code until it passes. For a critical problem, a
person in *urgent_approvers* comments */authorize-urgent-fix* on the issue
before the fix merges; the agent asks with a choice commented on the issue
(*agent/ask_person_tool.py --markdown*), each option naming its command. Once it is on the main branch, set the status to fixed;
the reporter comments */confirm-fixed*, and the issue is closed.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every problem has its block, following problem.v1 — at release every problem, on every pull request every problem a test names; an open report from the form, named by no test, has it once analysed | check_problem_record_gate · INCOMPLETE_PROBLEM_RECORD |
| R2 | A problem past the open status, or named by a test, states its cause, impact, severity, origin and escape | check_problem_record_gate · MISSING_ANALYSIS |
| R3 | At release, a high or critical problem names its affected parties and when they were notified | check_problem_record_gate · MISSING_ALERT |
| R4 | The fix of a critical problem has /authorize-urgent-fix from a person in urgent_approvers, given before it reached the main branch | check_urgent_fix_gate · UNAUTHORIZED_URGENT_FIX |
| R5 | Every @problem marker names a problem issue | verify_problem_closure_gate · UNKNOWN_PROBLEM |
| R6 | At release, a problem marked fixed has a test that names it | verify_problem_closure_gate · MISSING_PROBLEM_TEST |
| R7 | At release, a closed problem has its test on the main branch, or names its change request | verify_problem_closure_gate · CLOSED_WITHOUT_FIX |
| R8 | At release, a closed problem has /confirm-fixed from its reporter, given after the fix | verify_problem_closure_gate · MISSING_CONFIRMATION |
| R9 | While a release is proposed, the report counts the problems opened, fixed and still open since the previous release, by severity, by component and by the stage they got through | report_problem_trends_gate · MISSING_TREND_SECTION |
| R10 | The cause is the real one, and the test reproduces the crack the reporter saw | Review |
| R11 | The origin and the escape are the real ones; an escape that is the framework's weakness has a framework feedback entry that names the problem | Review |

## Not checkable

- That the affected parties were really told — the record says when.
- Whether anyone acts on the trends — left to the organisation.

## Example

```yaml problem
what: The account locks after three failed sign-ins instead of five.
where: sign-in page, auth-service
reproduce: Sign in with a wrong password three times, then with the right one.
expected: The fourth attempt is accepted.
actual: The account is locked.
status: under-analysis
cause: The failure counter counts each attempt twice.
impact:
  requirements: [REQ-0047]
  components: [auth-service]
severity: high
origin: unit_construction
escape:
  stage: unit_tests
  why: The tests count the failures of one attempt, never of three in a row.
affected_parties: [the customer's support desk]
notified: 2026-10-12
```
