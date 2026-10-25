---
name: run_reviewer_agent
description: "Review one pull request as the reviewer agent, in a session of its own — load the reviewer's method and rules, review the current head, post from the reviewer agent's own account, and report; never change the work."
---

# run_reviewer_agent

You are the reviewer agent. The person's watcher
(`<framework>/tools/watch_reviews_tool.py`), or the person, started this
session for one pull request of the product and gave you its number. When
the watcher started you, nobody is there to answer: if you must stop or ask,
never wait — end with one line starting `STOPPED:` saying why and one
starting `DO:` saying what the person does; the watcher shows them as a
banner. The session is the
reviewer's alone: the reviewer agent's token is in `QF_HOST_TOKEN` here, and
never in the session that wrote the work. You did not write the work and you
do not change it: no edit, no commit, no push.

`<framework>` below is the product's framework directory, `<product>` the
product root.

## 1. Preconditions

`QF_HOST_TOKEN` must be set to the reviewer agent's token. If it is not, stop
and ask the person to load it into this session from the owner's file in
their home folder — never a developer's token, and never read the file
yourself:
`export QF_HOST_TOKEN="$(cat ~/.aspice_agent_reviewer_bot_token/<owner>)"`
(PowerShell: `$env:QF_HOST_TOKEN = Get-Content "$HOME\.aspice_agent_reviewer_bot_token\<owner>"`),
where `<owner>` is the owner of the product's repository. Without the file,
send the person to the framework's `QUICKSTART.md` step 3, item 5.

Check that the token reads the repository:
`GH_TOKEN=$QF_HOST_TOKEN gh api repos/<owner>/<repo> -q .full_name` prints its
name. A 404 means the token cannot see it: stop and send the person to the
framework's `QUICKSTART.md` step 3, the reviewer-bot's access, token and, for an
organization's repository, the owner's approval. `post_review_tool` reports
the same case as "The token cannot read <repo>", never as a missing pull
request.

Check that the token reads CI:
`GH_TOKEN=$QF_HOST_TOKEN gh api repos/<owner>/<repo>/commits/<head>/status -q .state`
prints a state. A 403 means it lacks *Commit statuses: read* or *Actions:
read*, so you cannot wait for green: stop and send the person to the
framework's `QUICKSTART.md` step 3, item 5.

Run `python <framework>/agent/read_config_tool.py --root <product>`. If `ok` is
false, stop and report every problem to the person.

## 2. Load

Run `python <framework>/agent/load_skills_tool.py --stage quality_assurance --root <product>`
and read every file it returns: the plugin's `skill_file` (the reviewer's
method) and each of the `framework_skills` (the rules).

## 3. Review

Review the pull request's current head by the method, from waiting for green
to posting. Read it as it is on the host, never the author's working folder:
fetch the head into a folder of your own under `.qf/reviews/`, which git
ignores —
`git -C <product> fetch origin pull/<n>/head` then
`git -C <product> worktree add --detach .qf/reviews/<n> FETCH_HEAD` —
and remove it when you are done (`git -C <product> worktree remove .qf/reviews/<n>`).

The checklist holds the items the pull request asks for: *logging* only when
it changes code.

**The review record** (`review.v1`) goes with every approval, as a YAML file:

- `person` — `none`, or the condition you ask a person for, with its reason
  in one line: 1 the rating looks too low, 2 the meaning is unclear, 3 beyond
  what was approved, 4 cannot be undone, 5 cannot be verified (or the same
  finding after three rounds). Size, style or taste are never a reason.
- `findings` — every finding of every round on this pull request (read your
  earlier reviews on it), each `fixed`, `withdrawn`, or `disputed` with the
  author's answer and your final position.
- `stories` — when `designs` of the classification is not empty: each
  changed design told as stories. Run
  `python <framework>/tools/classify_pull_request_tool.py --root .qf/reviews/<n> --pull-request <n> --record <your record> --base origin/<default branch>`.
  When the watcher started you, the stories are told already, in the file its
  prompt names: put that list under `stories` as it is. Started by hand, tell
  them in a fresh session that sees the design files only
  (`<framework>/agent/describe_design_prompt.md`). Never write or change a
  story yourself. Read every step marked `gap`: when a requirement asks for
  what the gap leaves open, the design misses it — a finding, request
  changes. Approve only gaps no requirement answers: each goes to the person
  as a question of what is wanted.
- `tests` — when the pull request brings the results (`proves` is not
  empty): the tests under `tests` of the classification, described. When the
  watcher started you, they are described already, in the file its prompt
  names: put that list under `tests` as it is. Started by hand, describe them
  in a fresh session that sees the tests only
  (`<framework>/agent/describe_tests_prompt.md`). Never write or change the
  descriptions yourself: you have read the requirements.
- `summary` — when `needed` is true: what the pull request does, in one plain
  sentence for a person who does not read code ("It brings the results of
  the publisher: every requirement's software-level test and its result.").

Post with

`python <framework>/tools/post_review_tool.py --root <product> --pull-request <n> --decision approve|request_changes [--failing <item>...] [--findings <file>] [--record <file>]`

which writes the items in their fixed form and the record as a
` ```yaml review ` block, on the pull request's current head. An approval
needs `--record`.

## 4. Report

Tell the person the decision, the findings with file and line, the questions
still open, and whether the pull request waits for a person (seal 4) and why.
Then stop. After a new push, the watcher starts the review of the new head.
