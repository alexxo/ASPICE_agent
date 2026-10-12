# Invalid example

A criterion that does not state its case.

```yaml requirement
uid: REQ-0101
level: system
kind: functional
criticality: medium
statement: A registered user signs out from any page.
acceptance_criteria:
  - given: a signed-in user
    when: the user selects sign out
    then: the session is closed
feasibility: Session store supports deletion.
size: S
environment: none
derived_from: auth-flow#web-app
```
