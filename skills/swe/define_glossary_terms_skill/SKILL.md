---
name: define_glossary_terms_skill
description: "Rules for the glossary: every domain term defined once, marked _term_ in requirements, used, and never replaced by an alias."
---

# skill: define_glossary_terms_skill

**Stage:** 2 · SWE.1 Software requirements
**Loaded with:** create_requirements_plugin
**Contract:** contracts/glossary_term_contract.v1.schema.json
**Gates:** check_glossary_gate
**Replaces:** domain-glossary (main)

## What it governs

The glossary: one canonical name and one definition for every domain term the
requirements use (SWE.1 BP3, correctness). It is written together with the
requirements, in the same stage, so a requirement never uses a term the
glossary does not define.

## Inputs

- **qf.yaml** — *paths.glossary_file* and *paths.requirements_dir*.
- The **existing glossary** and the **requirements** being written.
- On a retry: the **findings** of the previous attempt (*findings.v1*).

## Contract

- One file, *paths.glossary_file*. Headings and prose are free; only the
  fenced *yaml glossary_term* blocks are the contract.
- Each block is one term and validates against *glossary_term.v1*: *term*,
  *definition* (one sentence, present tense), optional *examples*, optional
  *aliases*.

**Marking.** In a requirement's statement and acceptance criteria, every domain
term is written between underscores — *_lockout_*, *_account block_* — exactly as
its *term* is spelled here (case aside). The mark is how the gate finds terms.
Underscores, not asterisks: a YAML value starting with an asterisk breaks the
file.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | The glossary file exists; every block validates against *glossary_term.v1* | check_glossary_gate · MISSING_GLOSSARY, SCHEMA_VIOLATION |
| R2 | Every term is defined once — terms and aliases compared without case | check_glossary_gate · DUPLICATE_TERM |
| R3 | Every marked term in a requirement is defined here | check_glossary_gate · UNDEFINED_TERM |
| R4 | A glossary term in a statement or criterion is always marked | check_glossary_gate · UNMARKED_TERM |
| R5 | Requirements use the canonical term, never an alias | check_glossary_gate · ALIAS_USED |
| R6 | Every term is used by at least one requirement | check_glossary_gate · UNUSED_TERM |
| R7 | A rename keeps the old name as an alias until no requirement uses it, then removes it | check_glossary_gate · ALIAS_USED, UNUSED_TERM |
| R8 | Every domain term is marked — a new term is never left as plain text | Checkpoint 2 |
| R9 | No synonyms: two terms never name the same concept | Checkpoint 2 |

## Not checkable

- Whether a word left unmarked is really a domain term (R8) — the gate only sees
  words it already knows.
- Whether two different terms really mean the same thing (R9).
- Whether a definition is precise enough to remove ambiguity.

## Example

```yaml glossary_term
term: lockout
definition: The state of an account that refuses every sign-in until it is unlocked.
examples:
  - An account is in lockout after five consecutive failed sign-ins.
aliases:
  - account block
```
