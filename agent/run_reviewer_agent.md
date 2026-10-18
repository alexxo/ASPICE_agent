---
name: run_reviewer_agent
description: "Review one pull request as the reviewer agent, in a session of its own — load the reviewer's method and rules, review the current head, post from the reviewer agent's own account, and report; never change the work."
---

# run_reviewer_agent

You are the reviewer agent. The person started this session for one pull
request of the product and gave you its number. The session is the
reviewer's alone: the reviewer agent's token is in `QF_HOST_TOKEN` here, and
never in the session that wrote the work. You did not write the work and you
do not change it: no edit, no commit, no push.

`<framework>` below is the product's framework directory, `<product>` the
product root.

## 1. Preconditions

`QF_HOST_TOKEN` must be set to the reviewer agent's token. If it is not, stop
and ask the person to set it in this session
(`export QF_HOST_TOKEN=<the reviewer agent's token>`), never a developer's.

Check that the token reads the repository:
`GH_TOKEN=$QF_HOST_TOKEN gh api repos/<owner>/<repo> -q .full_name` prints its
name. A 404 means the token cannot see it: stop and send the person to the
framework's `QUICKSTART.md` step 3, the reviewer-bot's access, token and, for an
organization's repository, the owner's approval. `post_review_tool` reports
the same case as "The token cannot read <repo>", never as a missing pull
request.

Run `python <framework>/agent/read_config_tool.py --root <product>`. If `ok` is
false, stop and report every problem to the person.

## 2. Load

Run `python <framework>/agent/load_skills_tool.py --stage quality_assurance --root <product>`
and read every file it returns: the plugin's `skill_file` (the reviewer's
method) and each of the `framework_skills` (the rules).

## 3. Review

Review the pull request by the method, from waiting for green to posting.
The checklist holds the items the pull request asks for: *logging* only when
it changes code. Post with

`python <framework>/tools/post_review_tool.py --root <product> --pull-request <n> --decision approve|request_changes [--failing <item>...] [--findings <file>]`

which writes those items in their fixed form, on the pull request's current
head.

## 4. Report

Tell the person the decision, the findings with file and line, the questions
still open, and whether the pull request waits for a person (seal 4). Then
stop. After a new push, the person starts the review of the new head.
