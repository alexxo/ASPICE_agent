---
name: expect_cases_prompt
description: "List the cases each acceptance criterion needs tested, from the criteria alone, never the tests or the code, so the reviewer agent can see which case no test checks."
---

# expect_cases_prompt

The watcher (`tools/watch_reviews_tool.py`) starts a fresh session with this
prompt before it reviews a pull request that brings the results — one that
adds or changes software-level tests, which name their requirements with
`@sdoc`. The session runs in a temporary folder outside the product that
holds only `criteria.yaml` — the statement and acceptance criteria of each
requirement those tests prove, each criterion numbered from 1 — and the
glossary, with the reading tool only and these instructions in the prompt, so
it has no path to the tests or the code. Without the watcher, the reviewer
agent starts it itself with those requirements, for example:

`claude -p "Follow <framework>/agent/expect_cases_prompt.md for REQ-0047 REQ-0048 of <product>: read only their criteria and the glossary"`

The list goes into the review record's `expected` (`review.v1`), and the
reviewer agent adds to each case the test that checks it, or `missing`. The
tester, the coder and the reviewer all read the same criteria next to the
tests; you read them without the tests, so a case they all left out shows.

## You

You are a tester who has not seen the tests. Read each criterion and list
what must be tested before you would believe it holds.

- **Never open a test, the code, a design or a diagram.** Read only
  `criteria.yaml` and the glossary.
- **Per criterion:** the case it states, then the limits (just below, at and
  just above a number; empty, first, last) and the failures it implies (the
  input refused, the service down, the action repeated). Only cases the
  criterion's words support: a case you would merely like is not expected.
- **One line per case**, in plain words with the values, so a person can
  read it: "a 3rd failed sign-in locks the account", not "boundary test".
- A criterion you can read two ways: list the case of each reading, and say
  so in the case ("if the lock is at the 3rd failure: …").

## Output

Only a YAML list, nothing before or after it, with at least one case for every
requirement in `criteria.yaml`:

```yaml
- requirement: REQ-0047
  criterion: 2
  case: a 3rd failed sign-in locks the account
- requirement: REQ-0047
  criterion: 2
  case: a right password on a locked account is refused
```
