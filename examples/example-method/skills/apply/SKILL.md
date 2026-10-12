---
name: apply
description: Stand-in method skill used by the Quality Framework's examples. Write the failing unit test first, then the code that turns it green.
---

# apply — stand-in method skill

**This is a stand-in, not a real method.** The Quality Framework is
method-agnostic: a real product fills this slot with its own method plugin.
The framework's examples and scenario tests use this skill so they run without
depending on an external method; in the scenario tests its output is scripted.

## Method

Write the failing unit test first, then the code that turns it green.

The form of the result is not defined here. The framework skills loaded next to
this one say what the work product must look like, and the gates check it.
