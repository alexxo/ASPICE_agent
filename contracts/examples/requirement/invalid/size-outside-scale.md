# Invalid example

Size outside S, M, L, XL.

```yaml requirement
uid: REQ-0101
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
size: XXL
environment: none
derived_from: auth-flow#web-app
```
