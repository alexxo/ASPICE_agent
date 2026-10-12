# Invalid example

```yaml component
id: auth-service
derived_from: auth-flow#auth-service
role: component
name: Auth service
responsibility: Checks credentials.
budget:
  - {resource: memory, value: 256, unit: MB}
size: M
meets: [REQ-0011]
modes: {not_applicable: ""}
concurrency: {not_applicable: Each request is handled on its own.}
```
