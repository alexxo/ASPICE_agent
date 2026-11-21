---
name: create_security_tests_skill
description: "Rules for security tests (principle #16): every interface crossing a trust boundary names the security test templates it needs, from the framework's catalog of five; the component at the product's end has a unit test, written first, for each template, marked @security[<template>], and every such test passes."
---

# skill: create_security_tests_skill

**Stage:** 3 · SWE.2 Software architecture (templates named); 5 and 6 (tested, passing)
**Loaded with:** create_architecture_plugin, create_unit_tests_plugin, create_unit_code_plugin
**Contract:** contracts/interface_contract.v1.schema.json
**Gates:** check_design_contract_gate, verify_test_first_gate, verify_security_tests_gate

## What it governs

The product's trust boundaries and their security tests. A component crosses a
trust boundary when it is the product's end of an interface whose other end is
*external* — where input from outside arrives, or a call leaves — or *runs_in:
untrusted* while it does not: a component of the product running where the
product does not control it, like a frontend in the visitor's browser, so
anyone can call what it calls. That interface names, in *security_templates*,
the templates of the catalog the boundary needs (stage 3); an interface
crossing no boundary names none, since no gate could require them. The tester writes, for each one, unit tests of the
component showing it resists what the template describes, red on the stubs
like every test (stage 5); the coder makes them pass and never edits them
(stage 6).

## Inputs

- The **architecture** — the external interfaces, what crosses them (*data*)
  and their protocol.
- The **requirements**, above all security ones, and their acceptance
  criteria.
- The **detailed design** — the units of each boundary component.
- On a retry: the **findings** of the previous attempt.

## Contract

On every ```yaml interface block (*interface.v1*) crossing a trust boundary, a
*security_templates* list: at least one template of the catalog, each once; on
no other. A ```yaml component block (*component.v1*) of the product running
where the product does not control it says *runs_in: untrusted*.
A test applying a template names it as *@security[&lt;template&gt;]* next to the
*@unit* marker of the unit it tests.

The catalog — what the tests of each template must show:

| Template | Pick it when | The tests show |
|---|---|---|
| *authentication* | Someone outside proves who they are here | A missing, wrong or expired credential is refused; a refusal does not tell which part was wrong; repeated failures are limited |
| *authorization* | What is allowed depends on who asks | Each action is refused to a caller without the right; a caller cannot reach another's data by changing an ID |
| *input-validation* | Data from outside is read here | Malformed, oversized, empty and out-of-range input is refused before use; input carrying code or queries (injection) is never run |
| *stored-data* | What arrives is stored, or stored data is sent out | Secrets are never stored or logged in clear; stored data is read back only by whom it belongs to |
| *outbound-calls* | The product calls a system outside it | A failing, slow or malformed answer is handled (time limit, refusal); no secret or personal data leaves beyond what the interface declares |

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | An interface names templates exactly when it crosses a trust boundary: at least one, each from the catalog and once | check_design_contract_gate · MISSING_SECURITY_TEMPLATES, TEMPLATES_WITHOUT_BOUNDARY, SCHEMA_VIOLATION |
| R2 | Every @security marker names a template of the catalog | verify_security_tests_gate · UNKNOWN_TEMPLATE |
| R3 | For every template an interface names, each component crossing the boundary through it has a passing unit test marked with it | verify_security_tests_gate · MISSING_SECURITY_TEST |
| R4 | The security tests are written first, by the tester, and fail on the stubs | verify_test_first_gate · TEST_NOT_FAILING |
| R5 | The templates fit what crosses the interface, and the tests really show what the template asks | Review |

## Not checkable

The architect confirms at checkpoint 1 that no trust boundary is missing from
the diagram; the reviewer agent at the pull request, and a person on the
important or risky pull requests (checkpoint 4), confirm:

- The templates named fit what crosses the interface — e.g. a form read from a
  browser needs *input-validation*.
- Every component running where the product does not control it (a browser, a
  mobile app, a customer's machine) says *runs_in: untrusted*.
- A test marked *@security* really shows what its template asks, not merely
  that the unit runs.
- No other boundary inside the product (e.g. between tenants) is left
  untested; the gates cover the external and untrusted ends only.

## Example

```yaml interface
id: browse
derived_from: auth-flow#browse
from: user
to: web-app
external: true
protocol: HTTPS from a browser
data: the sign-in form and its fields
security_templates: [authentication, input-validation]
implementations:
  real: the browser
  double: {kind: fake, name: scripted browser}
```
