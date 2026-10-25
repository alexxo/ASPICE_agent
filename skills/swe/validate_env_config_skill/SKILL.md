---
name: validate_env_config_skill
description: "Rules for environment variables (principle #23): declared with the detailed design, each with description, required, example and valid values; every variable the code reads is declared and every declared one is read; and every required one has a unit test, written first, showing start-up stops without it."
---

# skill: validate_env_config_skill

**Stage:** 4 · SWE.3 Software detailed design (declared); 5 and 6 (tested, read)
**Loaded with:** create_detailed_design_plugin, create_unit_tests_plugin, create_unit_code_plugin
**Contract:** contracts/env_variable_contract.v1.schema.json
**Gates:** check_detailed_design_contract_gate, check_env_config_gate

## What it governs

The environment variables the product's code reads — its configuration. They
are a design choice, so they are declared with the detailed design (stage 4),
in *qf.yaml paths.env_variables_file*. The tester then writes, for every
required one, a unit test showing the software stops at start-up when it is
missing or invalid (stage 5); the coder reads only declared variables, the way
the stack's read patterns describe (stage 6).

## Inputs

- The **detailed design** — which unit needs which value from where it runs.
- The **requirements**, above all constraints and security ones, for values
  that must not be built in.
- The **tech stack** — *env_read_patterns*, how the code reads a variable.
- **qf.yaml** — *paths.env_variables_file*.
- On a retry: the **findings** of the previous attempt.

## Contract

One ```yaml env_variable block (*env_variable.v1*) per variable in
*paths.env_variables_file*: its *name* as the code reads it, a *description*,
*required* (true: the software stops at start-up without it), an *example*
that works — never a real secret — and the *valid* values, with what happens
when an optional one is unset. A product whose code reads no variable has no
file.

The stack's *env_read_patterns* are regular expressions with one capture group
for the name, e.g. `os\.environ\[["']([A-Z0-9_]+)["']\]`. A test validating a
required variable names it as *@env[&lt;NAME&gt;]*.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every declaration can be read, follows its contract, and declares its name once | check_detailed_design_contract_gate · UNREADABLE_BLOCK, SCHEMA_VIOLATION, DUPLICATE_VARIABLE |
| R2 | Every read pattern is a regular expression with exactly one group | check_env_config_gate · INVALID_READ_PATTERN |
| R3 | Every variable the code reads is declared | check_env_config_gate · UNDECLARED_VARIABLE |
| R4 | Every declared variable is read by the code | check_env_config_gate · UNUSED_VARIABLE |
| R5 | Every @env marker names a declared variable | check_env_config_gate · UNKNOWN_VARIABLE |
| R6 | Every required variable is named by at least one passing unit test | check_env_config_gate · UNTESTED_VARIABLE |
| R7 | The tests show start-up really stops on a missing or invalid value, and no read has a name computed at run time | Review |

## Not checkable

The reviewer agent confirms at the pull request, and a person on the
important or risky pull requests (checkpoint 4):

- A test named with *@env* really shows the software stops at start-up when the
  variable is missing or invalid — not merely that it reads it.
- No variable is read with a name computed at run time, which no pattern finds.
- No example is a real secret.

## Example

```yaml env_variable
name: DATABASE_URL
description: Where the accounts and sessions are stored.
required: true
example: postgresql://localhost:5432/login
valid: a PostgreSQL connection URL
```
