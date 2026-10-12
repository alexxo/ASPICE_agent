# Login — requirements

Derived from the approved diagrams `auth-flow` (architecture) and `login`
(feature sequence), and from wish W-03.

## System level

```yaml requirement
uid: REQ-0011
level: system
kind: functional
criticality: high
statement: The web app shows a sign-in form to every visitor who is not signed in.
acceptance_criteria:
  - case: happy
    given: a visitor who is not signed in
    when: the visitor opens the web app
    then: the sign-in form is shown
  - case: edge
    given: a browser with scripts disabled
    when: the visitor opens the web app
    then: the form shows that scripts are required
feasibility: A static form; no external dependency.
size: S
environment: none
derived_from: auth-flow#web-app
```

```yaml requirement
uid: REQ-0012
level: system
kind: functional
criticality: high
statement: A registered user signs in to their _account_ with an email and a password.
acceptance_criteria:
  - case: happy
    given: a registered user with a valid password
    when: the user submits the sign-in form
    then: a session is opened
  - case: error
    given: a registered user
    when: the user submits a wrong password
    then: no session is opened and an error is shown
feasibility: Standard password authentication.
size: M
environment: none
derived_from: auth-flow#auth-service
```

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

```yaml requirement
uid: REQ-0014
level: system
kind: interface
criticality: medium
statement: The web app sends each sign-in request to the auth service.
acceptance_criteria:
  - case: happy
    given: a filled sign-in form
    when: the visitor submits it
    then: the auth service receives exactly one sign-in request
feasibility: One HTTPS call.
size: S
environment: none
derived_from: auth-flow#signin-request
```

## Software level

```yaml requirement
uid: REQ-0047
level: software
kind: security
criticality: high
statement: The auth service puts an _account_ in _lockout_ after five consecutive failed sign-ins.
acceptance_criteria:
  - case: happy
    given: an _account_ with 4 failed sign-ins
    when: a 5th sign-in fails
    then: the _account_ is in _lockout_
  - case: edge
    given: an _account_ in _lockout_
    when: the correct password is submitted
    then: the sign-in is refused
feasibility: A failure counter in the session store, reset on success.
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

```yaml requirement
uid: REQ-0048
level: software
kind: observability
criticality: medium
statement: The auth service logs the start and the outcome of every sign-in.
acceptance_criteria:
  - case: happy
    given: any sign-in
    when: it completes
    then: one auth.signin.end or auth.signin.error event is logged
feasibility: The structured logger is part of the stack.
size: S
environment:
  - element: log pipeline
    impact: about 3 events per sign-in
derived_from: login#auth-service
refines: REQ-0012
metric: sign-ins with a matching end or error event
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

```yaml requirement
uid: REQ-0049
level: software
kind: functional
criticality: high
statement: The sign-in form takes an email and a password.
acceptance_criteria:
  - case: happy
    given: the sign-in form
    when: the user fills in an email and a password
    then: the form can be submitted
  - case: error
    given: the sign-in form
    when: the email field is empty
    then: the form cannot be submitted
feasibility: Two input fields.
size: S
environment: none
derived_from: login#web-app
refines: REQ-0011
```

```yaml requirement
uid: REQ-0050
level: software
kind: interface
criticality: medium
statement: The auth service accepts the sign-in request as JSON over HTTPS.
acceptance_criteria:
  - case: happy
    given: a sign-in request as JSON
    when: it arrives over HTTPS
    then: the auth service answers with a session or an error
feasibility: A standard HTTP endpoint.
size: S
environment: none
derived_from: login#auth-service
refines: REQ-0014
```

```yaml requirement
uid: REQ-0051
level: software
kind: constraint
criticality: high
statement: The auth service is built for the Java 21 runtime.
acceptance_criteria:
  - case: happy
    given: the auth service build
    when: it is compiled
    then: it targets Java 21
  - case: error
    given: a build configured for Java 17
    when: the auth service is compiled
    then: the build fails
feasibility: The build tool supports Java 21.
size: S
environment: none
derived_from: W-03
refines: REQ-0013
```
