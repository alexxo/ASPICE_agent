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

Explain the three roles. Ask the person which GitHub account plays each one,
and keep the answers for step 5. This file calls them *reviewer*, *developer*
and *reviewer-bot*:

- **reviewer**: the person who reviews. Approves the pull requests the
  framework samples (every architecture change, every change to the CI file,
  `.gitmodules` or `qf.yaml`, and one in five of the others), the checkpoints,
  urgent fixes and change requests. Their account is the **code owner**, the
  **urgent approver** and the **change approver**. There can be several.
- **developer**: works with the agent and opens the pull requests. There can be
  several.
- **reviewer-bot**: the reviewer agent's own GitHub account, which posts the
  agent's reviews. Its approvals never count as a person's.

Then the person does, on GitHub:

1. Create the reviewer-bot account, if it does not exist.
2. Create an **empty** repository for the product: no README, no licence, no
   `.gitignore`.
3. Add every developer and the reviewer-bot as collaborators with **write**
   access. A review counts only from an account that can write.

Nothing else is configured on GitHub. There is no secret, no branch protection,
no mirror and no paid plan. CI reads GitHub with its own token, and every push
to `main` checks that each change came through a reviewed pull request with
passing gates.

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
  with its token in the agent's session: `export QF_HOST_TOKEN=<reviewer-bot's
  token>`.
- **reviewer** approves the sampled pull requests on GitHub, and gives the
  checkpoint decisions the agent asks for.
- **Everyone**: every change reaches `main` through a reviewed pull request
  with passing gates. Never push to `main` directly and never rewrite it (no
  force-push, no reset). CI flags a direct push and blocks the next release
  until the change is reverted or reviewed, and it catches a rewrite on the
  push itself.

The rules behind all of this are in `.framework/docs/ASPICE_agent_documentation.md`,
section *Starting a product*.
