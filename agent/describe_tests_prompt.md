---
name: describe_tests_prompt
description: "Describe each test of a pull request from the test alone, never the requirement, for the person's review (checkpoint 4): what it prepares, does and checks, and what it leaves out."
---

# describe_tests_prompt

The reviewer agent starts a fresh session with this prompt and the list of test
files the person reviews — the `tests` of `classify_pull_request_tool`'s
result — for example:

`claude -p "Follow <framework>/agent/describe_tests_prompt.md for these files: <file> <file>"`

The session's description goes into the review record's `tests`
(`review.v1`), and the person reads it next to the approved criteria. Because
it never saw them, a test that checks something other than its criterion shows
as a mismatch the person can see.

## You

You describe tests for a person who reads plain text and does not read code.
You see the test files only.

- **Never open a requirement, a design, a diagram or the code under test** —
  no file under the requirements, design, diagrams or architecture folders,
  and no file the tests import from the product. Describe what the test itself
  does, not what it is meant to do.
- If a test cannot be understood without another file, say so in *Not*; do not
  open it.

## For each test in the files

One entry, in this form, in plain words — values as the test sets them, no
code, no names of functions or classes unless the person would see them in
the product:

```yaml
- file: <the test file>
  test: <the test's name>
  prepares: <the starting situation, with its values>
  does: <the one action the test performs>
  checks: <what it requires of the result, with the values>
  not: <what a reader would expect it to check and it leaves out; "nothing obvious" if so>
```

A test that is switched off (skip, xfail, disabled) says so in *checks*.

## Output

Only the YAML list, nothing before or after it, so the reviewer agent can
paste it under `tests:` in its review record.
