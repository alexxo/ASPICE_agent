---
name: draw_diagram_skill
description: "Rules for the diagrams drawn first at SWE.2: every element identified and labelled, every flow connected, rules in the invariants file, the link to the wishes in the wishes file, the picture committed next to each diagram, and the architect's approval on the review page before requirements are derived."
---

# skill: draw_diagram_skill

**Stage:** 1 · SWE.2 Software architecture — diagram, drawn first
**Loaded with:** create_diagram_plugin
**Contract:** contracts/diagram_wishes_contract.v1.schema.json
**Gates:** check_diagram_contract_gate, verify_diagram_to_wishes_link_gate, verify_diagram_approval_gate

## What it governs

The diagrams drawn from the customer's wishes before anything else, and the two
files next to each one. The diagram plugin (e.g. Archify) brings the drawing and
its own format; this skill brings what the framework needs from the result, so
that requirements can be derived from it element by element. When the plugin's
habits disagree with these rules, the rules win: the gates read only what the
rules ask for.

## Inputs

- The **customer's wishes** (*W-01*, *W-02*, …), in *qf.yaml paths.wishes_file*.
- **qf.yaml** — *paths.diagrams_dir*.
- The **existing diagrams**, if any — grow them, do not redraw them.
- On a retry: the **findings** of the previous attempt; at checkpoint 1: the
  architect's comment.

## Two levels

The diagrams are drawn at two levels, set by their type:

- **System level** — an *architecture*, *workflow*, *dataflow* or *lifecycle*
  diagram: the picture people read at a glance, the parts and how they hand
  over to each other. Keep it a picture: the main hand-overs, not every step.
- **Software level** — a *sequence* diagram, one per feature: its steps in
  detail, message by message.

Each level is a source of requirements of its own level at SWE.1, and a step is
derived once, at the level that details it. Draw a step in detail in the
sequence diagram, not again in the picture.

## Contract

Per diagram, in *paths.diagrams_dir*, four files sharing its ID:

| File | Contract | Holds |
|---|---|---|
| *&lt;id&gt;.&lt;type&gt;.json* | the diagram tool's own (read through the adapter into *diagram.v1*) | The drawing: nodes, edges, messages |
| *&lt;id&gt;.invariants.yaml* | *invariants.v1* | The rules the drawing cannot show, *INV-&lt;n&gt;*, each naming the elements it constrains |
| *&lt;id&gt;.wishes.yaml* | *diagram_wishes.v1* | Which wishes each element realises |
| *&lt;id&gt;.&lt;type&gt;.html* | the diagram tool's own page | The picture the tool renders from the drawing, committed with it |

Next to them, one *review.html* for all the diagrams: the page the architect
reads at checkpoint 1, rendered by *agent/render_review_tool.py --checkpoint 1*,
never written by hand. It lists every element and its wishes next to each
picture, and marks what changed since the previous approval.

The ID is the file name up to its first dot, lower-case words joined by
hyphens (*login.sequence.json* → *login*). An element is referenced as
*&lt;id&gt;#&lt;element&gt;* — the form requirements will use in *derived_from*.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | There is at least one diagram | check_diagram_contract_gate · NO_DIAGRAMS |
| R2 | The file name is a valid diagram ID and the diagram tool's file can be read | check_diagram_contract_gate · INVALID_DIAGRAM_ID, UNREADABLE_DIAGRAM, UNSUPPORTED_DIAGRAM_TYPE |
| R3 | Every element has an ID and a label; every edge and message has both endpoints | check_diagram_contract_gate · MISSING_ID, MISSING_LABEL, MISSING_ENDPOINT |
| R4 | An ID is used once in a diagram | check_diagram_contract_gate · DUPLICATE_ID |
| R5 | Every edge and message connects nodes that exist | check_diagram_contract_gate · DANGLING_ENDPOINT |
| R6 | Every node takes part in at least one edge or message | check_diagram_contract_gate · ORPHAN_NODE |
| R7 | A rule the drawing cannot show goes in the invariants file and names only elements that exist | check_diagram_contract_gate · INVALID_INVARIANTS, INVARIANTS_FOR_OTHER_DIAGRAM, UNKNOWN_CONSTRAINED_ELEMENT |
| R8 | Every diagram has its wishes file, linking only elements and wishes that exist | verify_diagram_to_wishes_link_gate · MISSING_WISH_LINKS, INVALID_WISH_LINKS, UNKNOWN_ELEMENT, UNKNOWN_WISH |
| R9 | Every wish of kind behaviour is realised by an element of some diagram; a constraint need not be | verify_diagram_to_wishes_link_gate · NO_WISHES, UNCOVERED_WISH |
| R10 | The architect approves the diagrams at checkpoint 1 before any requirement is derived, and the approval covers their current content | verify_diagram_approval_gate · MISSING_APPROVAL, APPROVAL_OUTDATED, APPROVED_TOO_LATE, NOT_A_GIT_REPOSITORY |
| R11 | Every flow has its error path, and no flow is ambiguous | Checkpoint 1 |
| R12 | There is at least one system-level diagram and at least one sequence diagram | check_diagram_contract_gate · NO_SYSTEM_DIAGRAM, NO_SEQUENCE_DIAGRAM |
| R13 | Every wish of kind behaviour is realised by an element of a sequence diagram, so every feature reaches the software level | verify_diagram_to_wishes_link_gate · WISH_NOT_IN_SEQUENCE |
| R14 | The picture stays a picture: the parts and the main hand-overs, the steps in the sequence diagrams | Checkpoint 1 |
| R15 | Every diagram keeps its picture, committed with the diagram's last change or after it | check_diagram_contract_gate · MISSING_PICTURE, PICTURE_OUTDATED |
| R16 | The architect reviews on the review page, rendered from the current files; the approval covers the pictures and the page | verify_diagram_approval_gate · MISSING_REVIEW_PAGE, REVIEW_PAGE_OUTDATED |

## Not checkable

The architect confirms these at checkpoint 1:

- The diagram says what the wishes mean — the right elements, not only linked ones.
- Error paths are drawn, and no flow can be read two ways.
- The system-level picture does not repeat the sequence diagrams step by step.
- Every behaviour a wish asks for is either drawn or written as an invariant.

## Example

```yaml diagram_wishes
diagram: login
links:
  web-app: [W-01]
  auth-service: [W-01]
  INV-1: [W-02]
```
