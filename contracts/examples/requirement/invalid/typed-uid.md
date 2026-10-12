# Invalid example

Typed UID from main.

```yaml requirement
uid: REQ-FUNC-101
level: system
kind: functional
criticality: medium
statement: A registered user signs out from any page.
acceptance_criteria:
  - case: happy
    given: a signed-in user
    when: the user selects sign out
    then: the session is closed
feasibility: Session store supports deletion.
size: S
environment: none
derived_from: auth-flow#web-app
```
