# ADR-0001 — Java 21 for the auth service

The customer operates Java 21 only (W-03), so the language is a given; the
record keeps the alternative that was weighed and why it lost.

```yaml decision
id: ADR-0001
title: Java 21 for the auth service
status: accepted
date: "2026-10-05"
context: >-
  W-03 requires the software to run on the Java 21 runtime the customer already
  operates. The auth service holds the sign-in logic and the lockout state.
options:
  - name: Java 21 with Spring Boot
    pros: [runs on the customer's runtime, operations already know it]
    cons: [larger memory footprint per instance]
  - name: Go
    pros: [small binaries, low memory]
    cons: [a runtime the customer does not operate, breaks W-03]
choice: Java 21 with Spring Boot
consequences: >-
  Each auth-service instance is budgeted at 256 MB of memory; the build and
  every verification suite run through Maven.
```
