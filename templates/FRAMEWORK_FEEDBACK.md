# Framework feedback

Running log of Quality Framework weaknesses found while building this product
(principle #47). Copy it to the product as *qf.yaml paths.framework_feedback_file*;
*check_framework_feedback_gate* checks it on every pull request.

**What belongs here:** anything the framework claims that is not true, anything
it enforces that it should not, and anything it says it enforces and does not.
Evidenced findings only — a command that was run and the output it produced. A
finding only reasoned about is a hypothesis; say so in **Verification**.

**Do not patch around the framework locally.** Record the gap here and leave the
product in its honest state. A local workaround hides the defect from every
other product built on the framework. If you must unblock, name exactly what you
did in **Workaround applied** and mark it for removal.

**On every framework version bump** — a change of the submodule at
*paths.framework_dir* — record under **Log** what you found, in an entry whose
**Framework version** is the new version, or a line starting with it:
*No findings for v6.1.0 (a1b2c3d)*. Silence is indistinguishable from having
forgotten. Only these count: the framework's answers quoted here, and a version
named anywhere else, do not account for a bump.

## How to use this file

One `### FB-<n>` entry per finding, newest first under **Log**. Never edit a
closed entry: add a follow-up and link it. Fill every field; write `n/a` rather
than deleting one, so a missing answer stays visible.

| Severity | Meaning |
|---|---|
| critical | A gate reports success without checking: a green build that means nothing. |
| high | A declared gate has no implementation, or a document asserts something false. |
| medium | A contract defect, an incomplete fix, or two files disagreeing on one fact. |
| low | Friction, documentation, a missing capability with a workaround. |

| Class | Meaning |
|---|---|
| C1 | Silent bypass — a gate passes without reading its input |
| C2 | False claim — a document or configuration asserts what is not true |
| C3 | Unimplemented policy — a declared gate with nothing behind it |
| C4 | Contract defect — a schema or template wrong, ambiguous or unsafe |
| C5 | Missing capability |
| C6 | Friction or documentation |

## Entry template

```markdown
### FB-<n> — <one-line summary>

- **Date:** YYYY-MM-DD
- **Framework version:** <tag> @ <submodule SHA>
- **Severity:** critical | high | medium | low
- **Class:** C1 | C2 | C3 | C4 | C5 | C6
- **Status:** open | reported | fixed upstream in <version> | wontfix | superseded by FB-<n>

**What the framework claims** — quote it, with the file and line.

**What actually happens** — the command that was run and its output.

**Reproduction** — the smallest input that shows it.

**Verification** — run, or only read? Running is evidence; reading is a hypothesis.

**Blast radius** — this product only, or every product on the framework?

**Impact on this product** — what it broke, paused or shipped anyway.

**Workaround applied** — none, or the exact files, marked for removal.
```

## Log

<!-- Newest first. -->
