# Architecture — auth flow, interfaces

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
