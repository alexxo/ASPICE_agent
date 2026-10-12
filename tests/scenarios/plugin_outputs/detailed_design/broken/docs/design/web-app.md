# Web app — detailed design

Units of the component *web-app* (architecture: auth-flow), derived from its
structure diagram *web-app.architecture.json*. One unit, so no sequence diagram.

```yaml unit
id: signin-form
derived_from: web-app#signin-form
name: Sign-in form
responsibility: Shows the sign-in form, sends the credentials and shows the result.
inputs:
  - {name: email, type: string, range: not applicable, unit: not applicable}
  - {name: password, type: string, range: not applicable, unit: not applicable}
outputs:
  - {name: message, type: string, range: not applicable, unit: not applicable}
```
