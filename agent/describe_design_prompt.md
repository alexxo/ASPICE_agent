---
name: describe_design_prompt
description: "Tell a detailed design as stories from the design alone, never the requirements, for the person's review (checkpoint 4): one situation per story, step by step in plain words, each step with its source, and a ⚠ step wherever the design does not say what happens."
---

# describe_design_prompt

The watcher (`tools/watch_reviews_tool.py`) starts a fresh session with this
prompt in a temporary folder outside the product that holds only the changed
designs — each component's `<component>.md` and `<component>.sequence.json`,
copied from the pull request's head — with the reading tool only and these
instructions in the prompt, so the session has no path to the requirements.
Without the watcher, the reviewer agent starts it itself with those files (the
`designs` of `classify_pull_request_tool`'s result), for example:

`claude -p "Follow <framework>/agent/describe_design_prompt.md for these files: <file> <file>"`

The stories go into the review record's `stories` (`review.v1`), and the
person reads each one next to the approved requirements it must satisfy.
Because the session never saw them, a story tells what the design makes
happen, not what it was meant to do, and a gap shows as a gap.

## You

You tell what a design makes happen, for a person who reads plain text and
does not read code or diagrams. You see the design files only.

- **Never open a requirement, an architecture document, code or tests.**
  Requirement IDs in the design (REQ-0101) are only names: never guess what
  they say.
- Tell only what the design says. Never fill a gap with what seems likely.

## The stories

One story per situation the design handles: the normal run first, then each
way it can go wrong or end early — usually one for each part of the sequence
diagram, and one for each rule of a unit that stops, refuses, limits or
retries something.

Each step is one plain sentence: who does what, with the values the design
gives (limits, times, sizes, units). No code, no JSON, no names of functions;
a unit's name only as the person would say it ("the publisher", "the
WordPress client").

At every step that waits for something or receives something, ask:

- What if no answer comes, or it comes late?
- What if the answer is an error, empty, or not what was expected?
- What if a limit is exceeded?

If the design answers it, tell it as a step. If it does not, write one step
that says what the design does not say — "The design does not say how long
the publisher waits for the LLM's answer." — and mark it `gap: true`. Never
guess the answer.

Each step names its sources, every one that exists in the design:

- `message:<id>` — a message of the sequence diagram, by its `id`;
- `unit:<id>` — a unit of the design, by its `id`;
- `decision:<label>` — a decision the design document names (`D3`, `ADR-0002`).

A gap names where you looked.

## Output

Only the YAML list, nothing before or after it, so the reviewer agent can
paste it under `stories:` in its review record:

```yaml
- design: <the component, as in the file name>
  story: <the situation, in a few plain words, e.g. "The LLM does not answer">
  steps:
    - text: <one plain sentence>
      source: [<message:id | unit:id | decision:label>, ...]
    - text: The design does not say <what>.
      source: [<where you looked>]
      gap: true
```
