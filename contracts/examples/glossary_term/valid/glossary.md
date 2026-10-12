# Glossary

Every domain term used in a requirement is defined here exactly once.

```yaml glossary_term
term: account
definition: The record that identifies one registered user and holds their credentials.
```

```yaml glossary_term
term: lockout
definition: The state of an account that refuses every sign-in until it is unlocked.
examples:
  - An account is in lockout after five consecutive failed sign-ins.
aliases:
  - account block
```
