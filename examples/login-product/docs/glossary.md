# Glossary

Every domain term a requirement uses is defined here once, and written
`_term_` in the requirements.

```yaml glossary_term
term: account
definition: The record that identifies one registered user and holds their credentials.
```

```yaml glossary_term
term: lockout
definition: The state of an account that refuses every sign-in until it is unlocked.
examples:
  - An account is in lockout after five consecutive failed sign-ins.
```
