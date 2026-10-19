# Verification plan

```yaml verification_plan
contract: verification_plan.v1
unit:
  techniques: [boundary values]
  pass_fail_criteria: every selected unit test passes
  entry_criteria: [detailed design merged]
  exit_criteria: [every unit test passes]
  infrastructure: [pytest]
  selection: every unit test on every pull request
  regression: all unit tests run again
  coverage: {metric: lines, minimum: 80}
  suites:
    unit: {tool: pytest, run: pytest, results: build/unit.xml, test_files: ["**/test_*.py"]}
```
