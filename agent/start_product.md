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

Ask the person, one question at a time, and wait for each answer:

1. **The reviewer agent** — the code host account the reviewer agent posts its
   reviews from (`--reviewer-agent`).
2. **The urgent approvers** — the accounts that may authorize an urgent fix
   (`--urgent-approver`).
3. **The change approvers** — the accounts that may approve a change request
   (`--change-approver`).
4. **The code owners** — who must approve a change to the gates, the framework
   pin and the architecture: `@login`, `@org/team` or an e-mail
   (`--code-owner`).
5. **The mirror** — the URL of the second repository the product is mirrored to
   (`--mirror`).

Each of the first four may name several; repeat the flag once per name.
**Never invent a value, and never fill in a placeholder**: a value the person
did not give is a question you ask again.

## 3. Run the setup

Show the person the command with their answers, then run it:

`python <framework>/tools/create_product_tool.py --root <product> --reviewer-agent <login> --urgent-approver <login> --change-approver <login> --code-owner <owner> --mirror <url>`

- **Exit 0** — go to step 4.
- **Exit 2** — nothing was changed. Report every problem it printed, word for
  word, and what the person can do about it; ask again for a value it rejected,
  and run it again. Never delete, move or overwrite a file to get past a
  problem: that is the person's decision.
- **The framework's Python packages are missing** (PyYAML, jsonschema) — tell
  the person to install them with
  `python -m pip install -r <framework>/requirements.txt`, and wait.

## 4. Finish the setup with the person

Relay what the setup printed, and change none of it yourself:

- **The code host's steps** — the `QF_HOST_TOKEN` secret, the protected main
  branch with `gates` as a required check, and the mirror. Only the person
  changes the code host; the gates check the result later.
- **Plugins** — never install, update or remove a plugin yourself. When the
  setup reports a missing plugin, such as Archify, tell the person which one and
  where it was looked for, and wait.

Then show the person the files the setup wrote and staged
(`git -C <product> status --short`). With the person's approval, commit them:
`chore: start the product with the ASPICE framework <release>`.

## 5. Hand over

Follow `<framework>/agent/run_aspice_agent.md` from its step 1: the product is
at stage 1, which begins with the customer's wishes.
