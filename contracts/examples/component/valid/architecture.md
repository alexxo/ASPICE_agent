# Architecture — auth flow

Components and interfaces derived from the approved diagram `auth-flow`.

```yaml component
id: web-app
derived_from: auth-flow#web-app
role: component
name: Web app
responsibility: Shows the sign-in form and sends the credentials to the auth service.
budget:
  - {resource: page load time, value: 1.5, unit: s}
size: M
meets: [REQ-0010]
modes: {not_applicable: One mode; it starts ready and has no degraded operation.}
concurrency: {not_applicable: Each request is handled on its own; nothing is shared.}
composition_root: WebApp.main
```

```yaml component
id: auth-service
derived_from: auth-flow#auth-service
role: component
name: Auth service
responsibility: Checks credentials, opens sessions and locks accounts after failed sign-ins.
budget:
  - {resource: response time p95, value: 200, unit: ms}
  - {resource: memory, value: 256, unit: MB}
size: M
meets: [REQ-0011, REQ-0012, REQ-0013]
decisions: [ADR-0001]
modes:
  - {mode: start-up, to: [normal]}
  - {mode: normal, to: [degraded]}
  - {mode: degraded, to: [normal]}
concurrency: Sign-ins run in parallel; the failure counter of an account is updated atomically.
composition_root: AuthServiceApp.main
```

```yaml component
id: user
derived_from: auth-flow#user
role: external
name: User
responsibility: Signs in through a browser.
```
