# Quick start — a new product with the ASPICE Agent

You start a product in an empty folder, open your coding agent in it, and let
the agent walk you through the setup, one step at a time, until it hands the
product over to the ASPICE Agent for its first stage.

## For the person

1. Create the folder the product will live in, and open your agent there:

   ```sh
   mkdir my-product && cd my-product
   claude            # or any coding agent that can run commands
   ```

2. Tell the agent:

   > Follow the quick start at
   > https://raw.githubusercontent.com/alexxo/ASPICE_agent/main/QUICKSTART.md

The agent tells you what to do next. It runs the read-only checks and the
setup itself, and asks you before every change. Some steps are yours alone,
and it shows you the command and waits: installing anything, GitHub settings
and accounts, and global git settings.

---

## For the agent

You guide the person through the setup of a new product, then hand over to the
ASPICE Agent. Work through the steps below **in order, one at a time**. Say
what the step is for, do it or show the person what to do, check the result,
and only then go on. `<product>` is the folder you were started in; the
framework will be its git submodule at `<product>/.framework`.

**Rules for the whole setup:**

- **Never install, update or remove anything yourself**: no package, no
  plugin, no tool. Check whether it is already there first, for every Python on
  the machine (`which -a python3`), not only the first on the `PATH`. If it is
  missing, show the person the command and wait.
- **Never change a global setting or the code host yourself**: no
  `git config --global`, no GitHub account, repository, collaborator or
  setting. Show the person what to do and wait.
- **Never invent a value.** A name you were not given is a question you ask.
- **Ask before every change to the folder**, and show what will change.
- A step that fails: report the output word for word and what the person can
  do, then wait. Never work around it. A weakness of the framework goes into
  `<product>/FRAMEWORK_FEEDBACK.md` once it exists (step 5).

### Step 1 — Where are we?

- `<product>/qf.yaml` exists: the product is already set up. Go to step 9.
- `<product>/.framework` exists without `qf.yaml`: the framework was fetched,
  the setup was not run. Go to step 5.
- The folder holds other files: ask the person whether this is the product
  folder before going on. The setup never overwrites a file.
- The folder is empty: go on.

### Step 2 — What the machine needs

Check, and report what is missing:

| Needed | Check |
|---|---|
| git | `git --version` |
| Python 3.10 or later | `python3 --version` |
| PyYAML and jsonschema, the framework's runtime | `python3 -c 'import yaml, jsonschema'` |
| Node 18 or later, for the diagram plugin Archify | `node --version` |

For PyYAML and jsonschema, the person runs
`python3 -m pip install -r .framework/requirements.txt` after step 4 (in a
virtual environment if they prefer one).

### Step 3 — People and accounts

Explain the roles. Ask the person which GitHub account plays each one, and
keep the answers for step 5. This file calls them *reviewer*, *developer* and
*reviewer-bot*:

- **reviewer**: the person who reviews. Approves the pull requests the
  framework samples (every architecture change, every change to the CI file,
  `.gitmodules` or `qf.yaml`, and one in five of the others), the checkpoints,
  urgent fixes and change requests.
- **developer**: works with the agent and opens the pull requests.
- **reviewer-bot**: the reviewer agent's own GitHub account, which posts the
  agent's reviews. Its approvals never count as a person's.

**Three accounts are enough.** The setup in step 5 asks for four values, but
one account can fill several of them:

| The setup asks for | Filled by |
|---|---|
| reviewer agent | the **reviewer-bot** account |
| code owner | the **reviewer** account |
| urgent approver | the **reviewer** account |
| change approver | the **reviewer** account |

So the minimum is three GitHub accounts: one reviewer, one developer and one
reviewer-bot. The three must be different accounts. GitHub never lets the
author of a pull request approve it, so the person who approves the
developer's pull requests needs an account of their own, and the reviewer
agent posts from its own account so its reviews never count as a person's.
A larger team may name several accounts for any role, and may give the code
owner, urgent approver and change approver roles to different people.

Then the person does, on GitHub:

1. Create the reviewer-bot account, if it does not exist: its own e-mail, and
   two-factor authentication if the organization requires it.
2. Create an **empty** repository for the product: no README, no licence, no
   `.gitignore`.
3. Give every developer and the reviewer-bot **write** access. A review counts
   only from an account that can write.
   - *Personal repository:* repository → Settings → Collaborators → *Add
     people* → *Write*.
   - *Organization's repository:* an organization owner invites each account
     as a **member** (the organization → People → *Invite member*), then gives
     it write on the repository (repository → Settings → Collaborators and
     teams → *Add people* → *Write*). Make the reviewer-bot a member, not an
     outside collaborator: GitHub limits fine-grained tokens for outside
     collaborators.

   Signed in as each account, accept the invitation (the e-mail, or
   `https://github.com/orgs/<org>/invitation`).
4. *Organization's repository only*, once, by an organization owner: the
   organization → Settings → Third-party Access → Personal access tokens →
   Settings: allow access via **fine-grained** tokens, and choose whether they
   need an owner's approval.
5. Signed in as the reviewer-bot, create its token: Settings → Developer
   settings → Personal access tokens → Fine-grained tokens → *Generate new
   token*.
   - *Name and expiry:* e.g. *qf-reviewer <repository>*; note the expiry date,
     since the reviewer cannot post once the token expires.
   - *Resource owner:* the repository's owner: the **organization** for an
     organization's repository (offered only once the bot is a member), the
     bot's own account otherwise.
   - *Repository access:* *Only select repositories* → the product's
     repository.
   - *Repository permissions:* **Pull requests: read and write** and
     **Contents: read**, nothing else. It can review, but not push or merge.

   Copy the token once and keep it in a password manager, never in the
   developer's session or a file in the repository.
6. *Organization's repository, if item 4 asks for approval:* an organization
   owner opens the organization → Settings → Third-party Access → Personal
   access tokens → *Pending requests*, checks that the reviewer-bot's request
   asks only for the product's repository with those two permissions, and
   *Approves* it. Until then the token reads only public resources, so a
   private repository answers as if it did not exist.
7. Check the token, in a terminal that is not the developer's session:
   `GH_TOKEN=<token> gh api repos/<owner>/<repo> -q .full_name` prints the
   repository's name. A 404 means item 3, 5 or 6 is missing.

When the token expires, the reviewer-bot creates a new one (item 5), approved
again (item 6).

If GitHub does not offer the repository for a fine-grained token, a classic
token with the `repo` scope works and needs no organization approval, but it
reaches every repository the reviewer-bot can write to; the separate session
still keeps it out of the developer's.

Nothing else is configured on GitHub beyond these steps: there is no secret, no
branch protection, no mirror and no paid plan. CI reads GitHub with its own
token, and every push to `main` checks that each change came through a reviewed
pull request with passing gates.

### Step 4 — Fetch the framework at its latest release

Find the latest release, the highest `v<major>.<minor>.<patch>` tag:

```sh
git ls-remote --tags --refs https://github.com/alexxo/ASPICE_agent.git 'v*'
```

With the person's approval, clone it into the product folder:

```sh
git clone --branch v<latest> https://github.com/alexxo/ASPICE_agent.git .framework
```

Then have the person install the framework's runtime if step 2 found it missing:
`python3 -m pip install -r .framework/requirements.txt`.

### Step 5 — Run the setup

Follow `.framework/agent/start_product.md`. It asks for the values of step 3,
runs the construction site setup, and commits the result with the person's
approval. The setup writes `qf.yaml`, the CI workflows, `CODEOWNERS`, the
framework feedback log and the `.gitignore` lines, and stages the framework's
pin.

If the folder belongs to another account than the one running you, the setup
stops before changing anything and names both accounts. The person then either
runs the setup as the folder's owner, or lets git trust the folder for the
running account with a global git setting they run themselves:
`git config --global --add safe.directory <product>`.

Come back here when `start_product.md` reaches its step 5, instead of handing
over: the next steps finish the setup.

### Step 6 — Push the first commit

Show the person the commands, with the repository of step 3:

```sh
git branch -M main
git remote add origin <repository URL>
git push -u origin main
```

The pushing account needs write access. With read access only, GitHub answers
*Write access to repository not granted*.

### Step 7 — Install the diagram plugin Archify

[Archify](https://github.com/tt-a1i/archify) draws the diagrams of stage 1.
It is a complete tool: its `archify/` folder holds the agent's instructions
(`SKILL.md`) and the command-line tool that renders and checks the diagrams. It
needs Node 18 or later and no npm packages. The person installs it in their own
clone, for this product only. `.gitignore` excludes `.claude/`, so it is never
committed, and `.archify/`, its working folders (drafts, previews).

Show the person these commands. They pick an Archify release tag, e.g.
`v3.1.0`:

```sh
TMP=$(mktemp -d)
git clone --depth 1 --branch <archify release> https://github.com/tt-a1i/archify.git "$TMP/archify"
mkdir -p .claude/skills
cp -R "$TMP/archify/archify" .claude/skills/archify
rm -rf "$TMP"
```

Then check, yourself:

```sh
node .claude/skills/archify/bin/archify.mjs doctor
python3 .framework/agent/read_config_tool.py --root .
```

The second command must report no `PLUGIN_NOT_INSTALLED`. Another agent host
looks for skills in `.agents/skills`; a plugin installed anywhere else is named
in `.qf/environment.yaml` (see the README of `examples/login-product`).

### Step 8 — Every developer keeps a clone

Tell the person: every developer keeps a clone of the product with the
framework fetched. These clones are the product's backup.

```sh
git clone --recurse-submodules <repository URL>
# or, in an existing clone:
git submodule update --init
```

Each developer installs Archify in their own clone (step 7).

### Step 9 — Hand over to the ASPICE Agent

The person restarts the agent in the product folder, so it loads the Archify
skill. Then they say:

> Follow `.framework/agent/run_aspice_agent.md`.

From here the ASPICE Agent leads, stage by stage, starting with the customer's
wishes. Tell the person how the work runs from now on:

- **developer** opens the agent in the product folder and asks it to follow
  `run_aspice_agent.md`.
- **reviewer-bot**: the reviewer agent posts its reviews from this account,
  in a session of its own, never the developer's. For every pull request the
  agent asks for it, the developer opens a second session in the product
  folder, sets `export QF_HOST_TOKEN=<reviewer-bot's token>` there only, and
  asks it to follow `.framework/agent/run_reviewer_agent.md` for that pull
  request.
- **reviewer** approves the sampled pull requests on GitHub, and gives the
  checkpoint decisions the agent asks for.
- **Everyone**: every change reaches `main` through a reviewed pull request
  with passing gates. Never push to `main` directly and never rewrite it (no
  force-push, no reset). CI flags a direct push, or a merge with red gates or
  missing reviews, and blocks the next release until an urgent approver
  accepts the change after the fact: a non-conformance issue names it, and
  they comment `/accept-delivery` on it (a revert alone does not clear it).
  CI catches a rewrite on the push itself.

The rules behind all of this are in `.framework/docs/ASPICE_agent_documentation.md`,
section *Starting a product*.
