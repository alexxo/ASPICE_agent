# Login

Requirements derived from the approved diagrams `auth-flow` (architecture) and
`login` (feature sequence). Prose like this paragraph is free; only the
`yaml requirement` blocks are the contract. Domain terms in statements and
criteria are marked `_term_` and defined in the glossary.

## Sign-in

```yaml requirement
uid: REQ-0012
level: system
kind: functional
criticality: high
statement: A registered user signs in with an email and a password.
acceptance_criteria:
  - case: happy
    given: a registered user with a valid password
    when: the user submits the sign-in form
    then: a session is opened and the dashboard is shown
  - case: error
    given: a registered user
    when: the user submits a wrong password
    then: no session is opened and an error is shown
feasibility: Standard password authentication; no external dependency.
size: M
environment: none
derived_from: auth-flow#auth-service
```

## Platform

```yaml requirement
uid: REQ-0013
level: system
kind: constraint
criticality: high
statement: The software runs on the Java 21 runtime the customer operates.
acceptance_criteria:
  - case: happy
    given: the release build
    when: it is started on the customer's Java 21 runtime
    then: it starts without errors
  - case: error
    given: a Java 17 runtime
    when: the release build is started
    then: it stops with a message naming Java 21
feasibility: Java 21 is a current long-term-support release.
size: S
environment:
  - element: customer application servers
    impact: one Java 21 process per instance
derived_from: W-03
```

## Lockout

```yaml requirement
uid: REQ-0047
level: software
kind: security
criticality: high
statement: The auth component locks an _account_ after five consecutive failed sign-ins.
acceptance_criteria:
  - case: happy
    given: a user with 4 failed sign-ins
    when: a 5th sign-in fails
    then: the _account_ is in _lockout_
  - case: edge
    given: an _account_ in _lockout_
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
  instrument: integration
  window: one test run
  sample: 10 accounts
```

## Observability

```yaml requirement
uid: REQ-0048
level: software
kind: observability
criticality: medium
statement: The auth component logs every sign-in attempt and its outcome.
acceptance_criteria:
  - case: happy
    given: any sign-in attempt
    when: it completes
    then: one auth.signin.end or auth.signin.error event is logged with the account ID
feasibility: Structured logger already in the stack.
size: S
environment:
  - element: log pipeline
    impact: about 3 events per sign-in
derived_from: login#auth-service
refines: REQ-0012
metric: sign-in attempts with a matching end or error event
threshold: "== 100 %"
measurement_method:
  instrument: integration
  window: one test run
  sample: every acceptance criterion of REQ-0047
events:
  - auth.signin.start
  - auth.signin.end
  - auth.signin.error
watched_by:
  - alert on more than 50 auth.signin.error events per minute
```
