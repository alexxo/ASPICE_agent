# Invalid example

```yaml unit
id: count-failures
derived_from: auth-service#count-failures
name: Count failures
responsibility: Counts consecutive failed sign-ins.
inputs:
  - {name: failed attempts, type: int, range: {min: 0, max: 5}, unit: not applicable}
outputs: []
```
