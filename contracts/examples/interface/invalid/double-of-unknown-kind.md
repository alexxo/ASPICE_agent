# Invalid example

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
  double: {kind: dummy, name: auth service that answers yes}
```
