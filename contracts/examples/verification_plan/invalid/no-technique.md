# Verification plan

```yaml verification_plan
contract: verification_plan.v1
unit:
  techniques: []
  pass_fail_criteria: every selected unit test passes
  entry_criteria: [detailed design merged]
  exit_criteria: [every unit test passes]
  infrastructure: [pytest]
  selection: every unit test on every pull request
  regression: all unit tests run again
  on_change: selected
  coverage: {metric: lines, minimum: 80}
```
