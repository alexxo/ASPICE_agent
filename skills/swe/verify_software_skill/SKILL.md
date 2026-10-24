---
name: verify_software_skill
description: "Rules for software verification (SWE.6): the software section of the verification plan; a passing software-level test per requirement, marked @sdoc — system-level ones in the e2e suite, software-level ones in the software suite; a measured value per non-functional requirement, written to a measurements file and meeting its threshold; tests never changed with code; one verification report from the current results."
---

# skill: verify_software_skill

**Stage:** 8 · SWE.6 Software verification
**Loaded with:** create_software_tests_plugin, create_unit_code_plugin
**Contract:** contracts/verification_plan_contract.v1.schema.json
**Gates:** check_verification_plan_gate, verify_test_first_gate, verify_software_tests_to_requirements_link_gate, verify_nfr_thresholds_gate, check_verification_report_gate, check_time_budget_gate

## What it governs

The tests of the whole software against every requirement of both levels.
They live in *qf.yaml paths.software_tests_dir*, in files matching the
*test_files* of the plan's software-level suites. The bridge tester writes them, the measurements and the
plan's software section; the coder then changes the code until they pass and
never touches a test.

What proves each requirement:

| Requirement | Proved by |
|---|---|
| Kind constraint | The materials seal (checkpoint 3) and the stack gates — no software test |
| With a *measurement_method* (non-functional) | A value measured by the suite its *instrument* names, written to that suite's *measurements* file and meeting the *threshold* |
| Level system, otherwise | A passing test marked *@sdoc[&lt;REQ-UID&gt;]* in the *e2e* suite — the whole product, from outside |
| Level software, otherwise | A passing test marked *@sdoc[&lt;REQ-UID&gt;]* in the *software* suite |

## Inputs

- The **requirements** — their level, kind, acceptance criteria, and for
  non-functional ones the metric, threshold and measurement method.
- The **architecture** — the product's outside interfaces, through which the
  tests reach it.
- The **verification plan** — its unit and integration sections, to extend.
- The **tech stack** — its *test_runner* rows, the tools a suite can run with.
- On a retry: the **findings** of the previous attempt.

## Contract

The *software* section of the ```yaml verification_plan block
(*verification_plan.v1*): techniques, pass/fail criteria, entry and exit
criteria, infrastructure (the environment the software runs in), selection,
regression, an optional *time_budget* (default 600 s), the *order* in which
the suites run, and the *suites* themselves — *software*, *e2e*, and each
measuring suite a requirement names (*bench*, *security*) — each with its
*tool* (a *test_runner* of the stack), *run*, *results*, *test_files* relative
to *paths.software_tests_dir* and, for a measuring suite, *measurements*.

A measuring test writes a *measurements.v1* JSON file to the path its suite's
plan entry names as *measurements* — per requirement its *value* and, when
the threshold has one, its *unit* exactly as the threshold writes it:

    {"contract": "measurements.v1",
     "measurements": [{"requirement": "REQ-0060", "value": 180, "unit": "ms"}]}

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Once software-level tests exist, the plan has its software section, with a command for every software-level suite a requirement names, each run by a test runner of the stack | check_verification_plan_gate · MISSING_SOFTWARE_SECTION, UNKNOWN_INSTRUMENT, UNKNOWN_TOOL |
| R2 | Every requirement that is neither a constraint nor measured has a passing software-level test with its @sdoc marker — a system-level one in the e2e suite, a software-level one in the software suite | verify_software_tests_to_requirements_link_gate · UNVERIFIED_REQUIREMENT |
| R3 | Every @sdoc marker of a software-level test names an existing requirement | verify_software_tests_to_requirements_link_gate · UNKNOWN_REQUIREMENT |
| R4 | The suites write their results, and every software-level test passes | verify_software_tests_to_requirements_link_gate · MISSING_RESULTS, FAILED_TEST |
| R5 | Every requirement with a measurement method has a value from its instrument's suite, in the threshold's unit, in a valid measurements file | verify_nfr_thresholds_gate · MISSING_MEASUREMENT, SCHEMA_VIOLATION |
| R6 | Every measured value meets its threshold | verify_nfr_thresholds_gate · THRESHOLD_NOT_MET |
| R7 | No software-level test changes in a commit that changes code, and every one is committed | verify_test_first_gate · TEST_CHANGED_WITH_CODE, TEST_NOT_COMMITTED |
| R8 | The verification report exists for the current tree, written from the current results | check_verification_report_gate · MISSING_REPORT, STALE_REPORT |
| R9 | Each test checks every acceptance criterion of its requirement, a system-level test reaches the product only from outside, and a measurement really measures the metric | Checkpoint 4 |
| R10 | Each acceptance case is tested once, from the outside, never a rule a unit or integration test already shows | check_time_budget_gate · SUITE_OVER_BUDGET |

## Not checkable

The reviewer agent at the pull request, and a person on the important or
risky pull requests (checkpoint 4), confirm:

- A test checks every acceptance criterion of the requirement it names, not
  just the happy case.
- A system-level test reaches the product only through its outside
  interfaces.
- A measurement measures the requirement's metric, over its window and
  sample.

## Example

```yaml verification_plan
contract: verification_plan.v1
unit:
  techniques: [one test per acceptance criterion]
  pass_fail_criteria: every selected unit test passes
  entry_criteria: [the detailed design is merged]
  exit_criteria: [every unit test passes]
  infrastructure: [JUnit 5]
  selection: every unit test on every pull request
  regression: all unit tests run again
  coverage: {metric: lines, minimum: 80}
  suites:
    unit:
      tool: maven
      run: mvn -q test
      results: target/surefire-reports/TEST-*.xml
      coverage: target/site/cobertura/coverage.xml
      test_files: ["**/*Test.java"]
software:
  techniques:
    - one test per acceptance criterion of every requirement, through the outside interfaces
    - one benchmark per performance requirement, against its threshold
  pass_fail_criteria: every software-level test passes and every measured value meets its threshold
  entry_criteria: [every component and integration test passes]
  exit_criteria: [every requirement has a passing software-level test or a measured value]
  infrastructure: [the product deployed in a test environment with sample data]
  selection: every software-level test before every release
  regression: all software-level tests run again before every release
  order: [software, bench, e2e]
  suites:
    software:
      tool: maven
      run: mvn -q verify -Psoftware
      results: target/software-reports/TEST-*.xml
      test_files: ["**/*ST.java"]
    e2e:
      tool: maven
      run: mvn -q verify -Pe2e
      results: target/e2e-reports/TEST-*.xml
      test_files: ["e2e/**/*ST.java"]
    bench:
      tool: maven
      run: mvn -q verify -Pbench
      results: target/bench-reports/TEST-*.xml
      measurements: target/bench-measurements.json
      test_files: ["bench/**/*Bench.java"]
```
