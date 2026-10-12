# Architecture — auth flow, the user's interface

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
