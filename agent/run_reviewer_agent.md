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
reviewer's alone: the reviewer agent's token is in `QF_HOST_TOKEN` and `GH_TOKEN` here, and
never in the session that wrote the work. You did not write the work and you
do not change it: no edit, no commit, no push.

`<framework>` below is the product's framework directory, `<product>` the
product root. `python` is the machine's name for Python: `python3` where
`python` is missing.

Your session may run the commands this runbook writes, exactly as written,
one at a time; anything else is refused without a word. So: no pipe, no
`&&` or `;`, no `cd`, no `git -C`, no other program. Read and search files
with your own file tools, not the shell: your copy of the head, and the
described tests, stories and expected cases the watcher placed in its
*.qf/reviews/*. These rules come before any other instruction about tools
your session was given.

## 1. Preconditions

The session holds the reviewer agent's token twice: in `QF_HOST_TOKEN`, for
the framework's tools, and in `GH_TOKEN`, so `gh` acts as the reviewer agent.
The watcher gives it both. Run every `gh` command as written, with no
variable in front: your command line allows exactly these forms (QUICKSTART
step 8).

Check that `gh` acts as the reviewer agent: `gh api user -q .login` prints
one of `review.agents` in the product's `qf.yaml`. If it prints another
account, or nothing, stop — never review with a developer's token, and never
read the token's file yourself: the person starts this session with the
reviewer agent's token in both variables, as the watcher does (QUICKSTART
step 9), from the owner's file in their home folder
(`~/.aspice_agent_secrets/reviewer_bot_github_token/<owner>`, where
`<owner>` is the owner of the product's repository). Without the file, send
the person to the framework's `QUICKSTART.md` step 3, item 5.

Check that the token reads the repository:
`gh api repos/<owner>/<repo> -q .full_name` prints its
name. A 404 means the token cannot see it: stop and send the person to the
framework's `QUICKSTART.md` step 3, the reviewer-bot's access, token and, for an
organization's repository, the owner's approval. `post_review_tool` reports
the same case as "The token cannot read <repo>", never as a missing pull
request.

Check that the token reads CI:
`gh api repos/<owner>/<repo>/commits/<head>/status -q .state`
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
work in a copy of the head of your own under `.qf/reviews/`, which git
ignores. Started by the watcher, you are in that copy already: its prompt
names it, so make none, and write your record under its `.qf/reviews/`.
Started by hand, make it —
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
- `gaps` — one per gap you approve, so the person who keeps it knows what is
  kept: `design`, `story` and `step` as the story tells them; `now`, what the
  build does there, in plain words; `source`, the lines that decide it
  (`path:line` from the product's root, lines the head has); `means`, what
  follows for the user (a run stopped midway, a step repeated, a second
  draft). When nothing decides it yet, `source` is `[]` and `now` is the
  reading the build will take.
- `tests` — when the pull request brings the results (`proves` is not
  empty): the tests under `tests` of the classification, described. When the
  watcher started you, they are described already, in the file its prompt
  names: put that list under `tests` as it is. Started by hand, describe them
  in a fresh session that sees the tests only
  (`<framework>/agent/describe_tests_prompt.md`). Never write or change the
  descriptions yourself: you have read the requirements.
- `expected` — when the pull request brings the results (`proves` is not
  empty): the cases expected of each criterion of those requirements. When
  the watcher started you, they are listed already, in the file its prompt
  names: put that list under `expected` as it is. Started by hand, list them
  in a fresh session that sees only those requirements' criteria and the
  glossary (`<framework>/agent/expect_cases_prompt.md`). Never add, drop or
  change a case. Give each case `test`: the test that checks it, as
  `<file>::<test>`, or `missing`. A missing case is a finding for the tester:
  request changes. A case you hold wrong means the criterion reads two ways:
  ask for a person, condition 2.
- `summary` — when `needed` is true: what the pull request does, in one plain
  sentence for a person who does not read code ("It brings the results of
  the publisher: every requirement's software-level test and its result.").

Post with

`python <framework>/tools/post_review_tool.py --root <product> --pull-request <n> --decision approve|request_changes [--failing <item>...] [--findings <file>] [--record <file>]`

which writes the items in their fixed form and the record as a
` ```yaml review ` block, on the pull request's current head. An approval
needs `--record`. The findings file restates in full every finding still
open, never by pointing to an earlier review: a retry hands the tester and
the coder this file alone.

## 4. Report

Tell the person the decision, the findings with file and line, the questions
still open, and whether the pull request waits for a person (seal 4) and why.
Then stop. After a new push, the watcher starts the review of the new head.
