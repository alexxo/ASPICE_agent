# Detailed design — auth service

Units of the component `auth-service`, derived from its design diagram
`auth-service.architecture.json`.

```yaml unit
id: check-credentials
derived_from: auth-service#check-credentials
name: Check credentials
responsibility: Compares the submitted password with the stored hash of the account.
inputs:
  - {name: email, type: string, range: not applicable, unit: not applicable}
  - {name: password, type: string, range: not applicable, unit: not applicable}
outputs:
  - {name: verified, type: bool, range: not applicable, unit: not applicable}
calls: [count-failures]
```

```yaml unit
id: count-failures
derived_from: auth-service#count-failures
name: Count failures
responsibility: Counts consecutive failed sign-ins and locks the account at the limit.
inputs:
  - {name: failed attempts, type: int, range: {min: 0, max: 5}, unit: count}
outputs:
  - {name: locked, type: bool, range: not applicable, unit: not applicable}
```

```yaml unit
id: open-session
derived_from: auth-service#open-session
name: Open session
responsibility: Opens a session for a verified account.
inputs:
  - {name: account, type: Account, range: not applicable, unit: not applicable}
outputs:
  - {name: session lifetime, type: int, range: {min: 60, max: 86400}, unit: s}
```
