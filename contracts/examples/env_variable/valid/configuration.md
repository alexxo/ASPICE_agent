# Configuration — login-product

The environment variables the units read, declared with the detailed design.

```yaml env_variable
name: DATABASE_URL
description: Where the accounts and sessions are stored.
required: true
example: postgresql://localhost:5432/login
valid: a PostgreSQL connection URL
```

```yaml env_variable
name: LOCKOUT_MINUTES
description: How long an account stays locked after five failed sign-ins.
required: false
example: "15"
valid: a whole number from 1 to 1440; 15 when unset
```
