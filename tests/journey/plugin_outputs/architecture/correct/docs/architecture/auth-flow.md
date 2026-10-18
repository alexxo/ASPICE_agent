# Auth flow — architecture

Derived from the approved diagram *auth-flow* and the requirements approved at checkpoint 2, on the stack approved at checkpoint 3 (ADR-0001).

## Components

```yaml component
id: web-app
derived_from: auth-flow#web-app
role: component
name: Web app
responsibility: Shows the sign-in form and the result of a sign-in.
budget:
- resource: memory
  value: 64
  unit: MB
size: M
meets:
- REQ-0049
modes: {not_applicable: One mode; it starts ready and has no degraded operation.}
concurrency: {not_applicable: Each request is handled on its own; nothing is shared.}
composition_root: WebApp.main
```

```yaml component
id: auth-service
derived_from: auth-flow#auth-service
role: component
name: Auth service
responsibility: Checks credentials, counts failed sign-ins and locks accounts.
budget:
- resource: memory
  value: 256
  unit: MB
size: M
meets:
- REQ-0047
- REQ-0048
- REQ-0050
- REQ-0051
decisions:
- ADR-0001
modes:
  - {mode: start-up, to: [normal]}
  - {mode: normal, to: [degraded]}
  - {mode: degraded, to: [normal]}
concurrency: Sign-ins run in parallel; the failure counter of an account is updated atomically.
composition_root: AuthServiceApp.main
```

## Interfaces

```yaml interface
id: signin-request
derived_from: auth-flow#signin-request
from: web-app
to: auth-service
external: false
protocol: HTTPS + JSON
data: email and password; the result of the sign-in
implementations:
  real: HTTPS client of the auth service
  double: {kind: stub, name: auth service stub}
```
