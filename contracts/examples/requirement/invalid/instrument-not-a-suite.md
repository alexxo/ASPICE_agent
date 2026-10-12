# Invalid example

Instrument written as a tool instead of a verification suite.

```yaml requirement
uid: REQ-0047
level: software
kind: security
criticality: high
statement: The auth component locks an account after five consecutive failed sign-ins.
acceptance_criteria:
  - case: happy
    given: a user with 4 failed sign-ins
    when: a 5th sign-in fails
    then: the account is locked
  - case: happy
    given: a locked account
    when: the user submits the correct password
    then: the sign-in is refused with the message "account locked"
feasibility: Failure counter kept in the session store, reset on success.
size: S
environment:
  - element: session store
    impact: one counter key per account, expiring after 24 h
derived_from: login#INV-1
refines: REQ-0012
metric: failed sign-ins accepted before lockout
threshold: "<= 5"
measurement_method:
  instrument: pytest-benchmark
  window: one test run
  sample: 10 accounts
```
