# Invalid example

Observability kind without events and watched_by.

```yaml requirement
uid: REQ-0101
level: system
kind: observability
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
metric: events per sign-out
threshold: "== 1"
measurement_method:
  instrument: integration
  window: one run
  sample: 5 sign-outs
derived_from: auth-flow#web-app
```
