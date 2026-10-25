---
name: ensure_testability_skill
description: "Rules for a testable architecture (principle #15): every component declares its one composition root, and every interface declares the real implementation of its 'to' end and a test double that replaces it."
---

# skill: ensure_testability_skill

**Stage:** 3 · SWE.2 Software architecture
**Loaded with:** create_architecture_plugin
**Contract:** contracts/interface_contract.v1.schema.json
**Gates:** check_testability_gate

## What it governs

Whether every component of the architecture can be tested on its own. A
component reaches the others only through the interfaces of the architecture;
for each interface there is a real implementation and a test double, so a test
can swap one for the other; and each component chooses its concrete
implementations in one place, its composition root, never inside its units.
This skill adds those declarations to the blocks *write_design_skill* governs.

## Inputs

- The **architecture** being written — its components and interfaces in
  *paths.architecture_dir*.
- The **approved tech stack**, for the names of real implementations and the
  test-double libraries it allows.

## Contract

Two fields on the blocks of the architecture:

- on every ```yaml interface block (*interface.v1*), *implementations*: the
  *real* implementation of its *to* end, and a *double* with its *kind* (stub,
  fake, in-memory or mock) and *name*;
- on every ```yaml component block of role component (*component.v1*),
  *composition_root*: the one place where its concrete implementations are
  chosen and wired (e.g. *AuthServiceApp.main*). An external has none.

The schema checks their shape; the gate checks they are there.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | There is an architecture to check | check_testability_gate · NO_ARCHITECTURE |
| R2 | Every component declares its composition root | check_testability_gate · MISSING_COMPOSITION_ROOT |
| R3 | Every interface, external ones included, declares the real implementation of its *to* end and a test double | check_testability_gate · MISSING_IMPLEMENTATIONS |
| R4 | Components reach each other only through these interfaces, and concrete implementations are created only in the composition root | Review |

## Not checkable

There is no code at stage 3. The reviewer confirms at the pull request
(checkpoint 4) that the declared double can really replace the real
implementation — same interface, no hidden dependency — and, once code exists,
that no unit creates a concrete implementation outside its composition root.

## Example

```yaml interface
id: signin-request
derived_from: auth-flow#signin-request
from: web-app
to: auth-service
external: false
protocol: HTTPS + JSON
data: email and password
implementations:
  real: HTTPS client of the auth service
  double: {kind: stub, name: auth service stub}
```
