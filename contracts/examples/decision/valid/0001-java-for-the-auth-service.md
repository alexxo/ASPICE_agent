# ADR-0001 — Java 21 and Spring Boot for the auth service

```yaml decision
id: ADR-0001
title: Java 21 and Spring Boot for the auth service
status: accepted
date: 2026-10-05
context: The customer operates only Java 21 runtimes (REQ-0004); sign-in must answer within 200 ms.
options:
  - name: Java 21 + Spring Boot
    pros: [runs on the customer's runtime, mature security libraries]
    cons: [higher memory use]
  - name: Go
    pros: [small footprint]
    cons: [not supported by the customer's operations]
choice: Java 21 + Spring Boot
consequences: Memory budget of 256 MB per instance; the team needs Spring Security knowledge.
```
