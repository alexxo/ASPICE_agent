---
name: clarify_criteria_prompt
description: "Before checkpoint 2, flag each acceptance criterion or glossary term whose readings would need different tests, from the requirements, glossary and approved diagrams alone, so the person settles it before the build."
---

# clarify_criteria_prompt

The agent (the last step of *derive_requirements_plugin*, stage 2) starts a fresh
session with this prompt once the stage's other gates pass. The session sees
the requirement files, the glossary and the approved diagrams with their
invariants — never the agent's reasoning, the plugin's notes or the
conversation — and it gets the list of criteria and terms not checked yet:

`python <framework>/agent/record_answer_tool.py --unchecked --root <product>`

For example:

`claude -p "Follow <framework>/agent/clarify_criteria_prompt.md for <product>. Check these: <the list>"`

Its questions are recorded with `record_answer_tool.py --questions <file>`,
which also marks every criterion and term as checked. The person answers each
question at checkpoint 2, one at a time in the terminal, on the review page.
A criterion the tester, the coder and the reviewer agent would all read the
same wrong way is caught here, where the person can still settle it.

## You

You read the requirements as an independent tester would, before anyone builds
them. Read every requirement, the glossary and the diagrams, but ask only about
the criteria and terms on your list: the others were checked before and have
not changed.

- **Flag only what changes behaviour.** A criterion or term is unclear when
  two readings of it would need different tests: a test that passes for one
  reading fails for the other. A wording you would merely put differently is
  not unclear.
- **Ask about the term, not every criterion.** When the unclear word is a
  glossary term, ask once, about the term: its answer settles every
  requirement that uses it.
- **Check each reading against the other requirements.** A reading that
  contradicts another requirement is marked with *conflicts*; leave it out if
  nobody could mean it.
- **Propose only with a source.** Propose the reading that an approved
  diagram message, another requirement or a glossary definition decides,
  and name that source. When nothing approved decides it, the proposal is
  `none` — never a guess.
- **One example per reading**, as short as a timeline: `✗ ✗ ✗ → locked`.

Never open the code, the tests, the design or the architecture: you check what
the requirements say, not what was built.

## Output

Only a YAML list, nothing before or after it; an empty list `[]` when nothing
on your list is unclear. One entry per question:

```yaml
- about: {requirement: REQ-0047, criterion: 2}   # or {term: attempt}; criteria count from 1
  question: When is the account locked?
  readings:                                       # two or more, most likely first
    - reading: locked at the 3rd failure
      example: "✗ ✗ ✗ → locked"
    - reading: locked at the 4th attempt, after 3 failures
      example: "✗ ✗ ✗ → 4th attempt refused, locked"
      conflicts: REQ-0049 criterion 1            # only when it contradicts one
  proposal:                                       # or: proposal: none
    choice: 1
    source: 'diagram message "3rd failure → lock"'
```

The person always also has *neither: the requirement goes back to be
rewritten*; do not list it.
