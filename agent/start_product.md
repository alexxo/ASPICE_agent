---
name: start_product
description: "Start a new product from a framework cloned into its folder — ask the person the values only they know, run the construction site setup, relay the code host's steps, commit with the person's approval, and hand over to run_aspice_agent for stage 1."
---

# start_product

You start a new product for the person, then hand over to the ASPICE Agent. The
person has cloned the framework at a release into the product folder, at
`.framework`, and asked you to follow this file. `<framework>` below is that
clone, `<product>` the folder that holds it.

**You decide nothing a tool can decide.** The construction site setup,
`<framework>/tools/create_product_tool.py`, checks the folder, the framework's
release and every value before it changes anything; you never work any of that
out yourself, never write the files it writes, and never run its git steps by
hand.

## 1. Is the product already started?

If `<product>/qf.yaml` exists, the product is set up: change nothing, and follow
`<framework>/agent/run_aspice_agent.md` from its step 1.

## 2. Ask the values only the person knows

Ask the person, one question at a time, and wait for each answer. Each is a
choice printed by `<framework>/agent/ask_person_tool.py`: an account you
found (the code host's login of this folder, for example) as the proposal,
and *another: I type it*, whose words follow; with none found, *I type it*
and *stop the setup for now*:

1. **The reviewer agent** — the code host account the reviewer agent posts its
   reviews from (`--reviewer-agent`).
2. **The people** — the accounts CI calls in when a pull request needs a
   person's review: the review comment mentions them (`--person`).
3. **The architect** — the one account that decides every checkpoint on its
   pull request, the release on behalf of the customer (`--architect`).
4. **The customer** — who the product is built for, by name; they need no
   code host account (`--customer`).
5. **The urgent approvers** — the accounts that may authorize an urgent fix
   (`--urgent-approver`).
6. **The change approvers** — the accounts that may approve a change request
   (`--change-approver`).
7. **The code owners** — who must approve a change to the gates, the framework
   pin and the architecture: `@login`, `@org/team` or an e-mail
   (`--code-owner`).

The people, the approvers and the code owners may name several; repeat the
flag once per name.
**Never invent a value, and never fill in a placeholder**: a value the person
did not give is a question you ask again.

## 3. Run the setup

Show the person the command with their answers, then run it:

`python <framework>/tools/create_product_tool.py --root <product> --reviewer-agent <login> --person <login> --architect <login> --customer <name> --urgent-approver <login> --change-approver <login> --code-owner <owner>`

- **Exit 0** — go to step 4.
- **Exit 2** — nothing was changed. Report every problem it printed, word for
  word, and what the person can do about it; ask again for a value it rejected,
  and run it again. Never delete, move or overwrite a file to get past a
  problem: that is the person's decision.
- **The folder belongs to another account** — git refuses it, and the setup
  says so before changing anything, naming both accounts. Give the person the
  two choices it printed: run the setup as the folder's owner, or let git trust
  the folder for the running account with the `git config --global` command it
  printed. That changes a global git setting, so the person runs it; never run
  it yourself. Then run the setup again.
- **A framework weakness met on the way** — record it before going on, in
  `<product>/FRAMEWORK_FEEDBACK.md`, started from
  `<framework>/templates/FRAMEWORK_FEEDBACK.md` if the product has none
  (`<framework>/skills/sup/report_framework_feedback_skill/SKILL.md`). The setup
  keeps an existing log and its entries.
- **The framework's Python packages are missing** (PyYAML, jsonschema) — tell
  the person to install them with
  `python -m pip install -r <framework>/requirements.txt`, and wait.

## 4. Finish the setup with the person

Relay what the setup printed, and change none of it yourself:

- **The code host** — nothing to configure there: CI reads it with its own
  token. Tell the person that every developer keeps a clone of the product with
  the framework submodule fetched: the clones are the copy if the repository
  is lost.
- **Plugins** — never install, update or remove a plugin yourself. When the
  setup reports a missing plugin, such as Archify, tell the person which one and
  where it was looked for, and wait.

Then show the person the files the setup wrote and staged
(`git -C <product> status --short`). With the person's approval, commit them:
`chore: start the product with the ASPICE framework <release>`.

## 5. Hand over

Follow `<framework>/agent/run_aspice_agent.md` from its step 1: the product is
at stage 1, which begins with the customer's wishes.
