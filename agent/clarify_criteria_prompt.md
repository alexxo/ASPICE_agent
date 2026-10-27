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
which also marks every criterion and term as checked and numbers the questions
in the review page's order. A criterion unchanged since the latest approval of
checkpoint 2 is not on the list: the person read it. At checkpoint 2 the
person accepts the questions with a proposal in one list and answers the
others one at a time in the terminal, on the review page.
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
- **Ask only what someone would notice.** Ask only when the author, or a
  system next to the product, would notice which reading was built, and a
  careful builder could build either. An edge case nobody would notice is
  not a question; leave it out.
- **Ask about the term, not every criterion.** When the unclear word is a
  glossary term, ask once, about the term: its answer settles every
  requirement that uses it.
- **One rule, one question.** When the same rule settles several criteria or
  terms — a text of only white space is empty — ask once, about the first,
  and name the others under `also`.
- **Check each reading against the other requirements.** A reading that
  contradicts another requirement is marked with *conflicts*; leave it out if
  nobody could mean it.
- **Propose only with a source.** Propose the reading that an approved
  diagram message, another requirement or a glossary definition decides,
  and name that source. Where none decides it but every tool of this kind
  behaves one way without being told — a text of only spaces is empty, rows
  are read in order, one sign-in serves the whole run — propose that reading
  with the source `convention: <that behaviour, in one line>` — also when
  you are not sure of it: the person is shown every convention they accept,
  marked, and can answer it again. The proposal is `none` only when the
  readings are equally likely and no convention prefers one.
- **A rewritten criterion.** A line of your list that says it was rewritten
  to settle a question: that reading is decided. Ask only about wording the
  rewrite added, never the settled question again in other words.
- **Tell it as a short story, in the person's words.** The person is shown,
  per answer, what they accept: write it so a person who reads no code
  follows it without the requirements open. No requirement ID, no criterion
  number, and no glossary term without its plain meaning — "the brief (the
  cell telling the AI what to write)".
  - `situation`: what the person does or sees when the question matters
    ("you type a wrong password three times").
  - each `reading`: what the product then does, as a sentence ("the account
    is locked at the 3rd failed sign-in").
  - each `means`: what that means for the person — what they see, or must
    do, afterwards ("you wait 15 minutes or ask an administrator").
  - each `label`: the reading in a few words, as the person selects it
    ("lock at the 3rd").
- **One example per reading**, as short as a timeline: `✗ ✗ ✗ → locked`.

Never open the code, the tests, the design or the architecture: you check what
the requirements say, not what was built.

## Output

Only a YAML list, nothing before or after it; an empty list `[]` when nothing
on your list is unclear. One entry per question:

```yaml
- about: {requirement: REQ-0047, criterion: 2}   # or {term: attempt}; criteria count from 1
  also: [{requirement: REQ-0051, criterion: 1}]   # only when the same rule settles others
  question: When is the account locked?
  situation: you type a wrong password three times
  readings:                                       # two or more, most likely first
    - reading: the account is locked at the 3rd failed sign-in
      label: lock at the 3rd
      example: "✗ ✗ ✗ → locked"
      means: your 3rd try already locks you out
    - reading: the account is locked at the 4th attempt, after 3 failures
      label: lock at the 4th
      example: "✗ ✗ ✗ → 4th attempt refused, locked"
      means: you get one more try, which is refused
      conflicts: REQ-0049 criterion 1            # only when it contradicts one
  proposal:                                       # or: proposal: none
    choice: 1
    source: 'diagram message "3rd failure → lock"'
```

The person always also has *neither: the requirement goes back to be
rewritten*; do not list it.
