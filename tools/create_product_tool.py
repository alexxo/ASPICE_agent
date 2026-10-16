"""Set up a new product: its qf.yaml, its CI, its code owners, around the pinned framework.

The product is the repository's root and the framework is only its git submodule
at .framework, checked out at a release tag. The person clones the framework at a
release into the product folder and runs the setup from that clone, so the
framework exists once (decisions 1 and 3 of starting a product):

    git clone --branch v1.4.0 <framework repository> my-product/.framework
    python my-product/.framework/tools/create_product_tool.py --root my-product \\
        --reviewer-agent LOGIN --urgent-approver LOGIN --change-approver LOGIN \\
        --code-owner @LOGIN-OR-@ORG/TEAM

The setup makes the folder a git repository if it is none, and adopts the clone
as the submodule at .framework with the clone's origin as its URL.

Every value only a person knows is a required flag, never a placeholder: the
agent asks the person and passes the answers (decision 2). The tool stages the
submodule's pin and writes qf.yaml, the CI workflows copied from
templates/github, the CODEOWNERS file, the framework feedback log and the
agent's .gitignore lines — no work product and no empty folder (decision 4). It
refuses to replace qf.yaml or overwrite any file, keeps a feedback log the
product already has, and checks everything before it changes anything, git's
trust in the folder included; a git step that still fails undoes the repository
the run created (decision 5). It commits nothing, and it never changes the code
host: the steps there are printed for the person (decision 6).
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from agent.read_config_tool import read_config  # noqa: E402
from agent.resolve_stage_tool import resolve_stage  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402

__all__ = ["COPIED", "PATHS", "SLOTS", "create_product", "product_config", "release_tag"]

FRAMEWORK = Path(__file__).resolve().parent.parent
FRAMEWORK_DIR = ".framework"
CODEOWNERS = ".github/CODEOWNERS"
IGNORED = (".qf/", ".agents/", ".claude/", ".archify/")  # .archify/: Archify's drafts
FEEDBACK = "FRAMEWORK_FEEDBACK.md"

PATHS = {
    "requirements_dir": "docs/requirements",
    "glossary_file": "docs/glossary.md",
    "wishes_file": "docs/wishes.md",
    "diagrams_dir": "docs/diagrams",
    "approvals_dir": "docs/approvals",
    "architecture_dir": "docs/architecture",
    "decisions_dir": "docs/decisions",
    "stack_file": "docs/architecture/stack.yaml",
    "detailed_design_dir": "docs/design",
    "code_dir": "src",
    "verification_plan_file": "docs/verification-plan.md",
    "env_variables_file": "docs/configuration.md",
    "integration_tests_dir": "it",
    "software_tests_dir": "st",
    "observability_dir": "observability",
    "framework_dir": FRAMEWORK_DIR,
    "ci_file": ".github/workflows/quality_gates.yml",
    "framework_feedback_file": FEEDBACK,
    "releases_dir": "releases",
    "validation_scenarios_dir": "validation/scenarios",
    "validation_records_dir": "validation/records",
}

SLOTS = {
    "create_diagram_plugin": "archify",
    "create_requirements_plugin": "quality-framework/derive_requirements_plugin",
    "create_architecture_plugin": "quality-framework/derive_architecture_plugin",
    "create_detailed_design_plugin": "quality-framework/derive_detailed_design_plugin",
    "create_unit_tests_plugin": "quality-framework/derive_unit_tests_plugin",
    "create_unit_code_plugin": "quality-framework/derive_unit_code_plugin",
    "create_integration_tests_plugin": "quality-framework/derive_integration_tests_plugin",
    "create_software_tests_plugin": "quality-framework/derive_software_tests_plugin",
    "review_pull_request_plugin": "quality-framework/derive_review_plugin",
    "create_validation_scenarios_plugin": "quality-framework/derive_validation_scenarios_plugin",
}

# Framework template → where the product keeps its copy.
COPIED = {
    "templates/github/quality_gates.yml": PATHS["ci_file"],
    "templates/github/release.yml": ".github/workflows/release.yml",
    "templates/FRAMEWORK_FEEDBACK.md": PATHS["framework_feedback_file"],
}

SETUP = """\
The product is the repository's root, and the framework its submodule at .framework,
checked out at a release; clone it into the product folder and run the setup from there:
  git clone --branch v<version> <framework repository> <product>/.framework
  python <product>/.framework/tools/create_product_tool.py --root <product> ..."""

SAMPLE_EVERY = 5
ESCALATE_AFTER_DAYS = 30
_RELEASE = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_OWNER = re.compile(
    r"^@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:/[A-Za-z0-9._-]+)?$|^[^@\s]+@[^@\s]+$"
)

HOST_STEPS = """\
Nothing needs configuring on the code host: CI reads it with its own token, and every
push to the main branch checks that each change came through a reviewed pull request
with passing gates. Keep a clone of the product, with the framework submodule fetched,
on every developer's machine: the clones are the copy if the repository is lost.
On this machine: install the diagram plugin Archify (github.com/tt-a1i/archify) where
your agent finds skills, or name its folder in .qf/environment.yaml.
Then review the new files, commit them, and start the agent with
{framework}/agent/run_aspice_agent.md: stage 1 begins with the customer's wishes."""


def product_config(args: argparse.Namespace) -> dict:
    """The qf.v1 configuration for the person's answers."""
    return {
        "contract": "qf.v1",
        "paths": dict(PATHS),
        "slots": dict(SLOTS),
        "review": {"agents": args.reviewer_agent, "sample_every": SAMPLE_EVERY},
        "urgent_approvers": args.urgent_approver,
        "change_approvers": args.change_approver,
        "escalate_after_days": ESCALATE_AFTER_DAYS,
    }


def _git(*command: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *command], cwd=cwd, capture_output=True, text=True)


def release_tag(framework: Path) -> str | None:
    """The release tag the framework checkout is at, if any."""
    tags = _git("tag", "--points-at", "HEAD", cwd=framework).stdout.split()
    released = sorted(t for t in tags if _RELEASE.match(t))
    return released[-1] if released else None


def _submodule_paths(root: Path) -> list[str]:
    found = _git("config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$", cwd=root)
    return [line.split(None, 1)[1] for line in found.stdout.splitlines() if " " in line]


def _origin(framework: Path) -> str:
    """The URL the framework clone came from; empty when it has none."""
    return _git("remote", "get-url", "origin", cwd=framework).stdout.strip()


def _adopted(root: Path) -> bool:
    """Whether the product is a git repository that declares the submodule already."""
    return (root / ".git").exists() and FRAMEWORK_DIR in _submodule_paths(root)


def _account(uid: int) -> str:
    try:
        import pwd

        return pwd.getpwuid(uid).pw_name
    except (ImportError, KeyError):
        return str(uid)


def _untrusted(root: Path) -> str | None:
    """Why git would refuse the folder, if it would: it belongs to another account
    and git's safe.directory does not name it."""
    if not hasattr(os, "getuid"):  # the ownership rule is git's on POSIX systems
        return None
    owner = root.stat().st_uid
    if owner == os.getuid():
        return None
    trusted = _git("config", "--get-all", "safe.directory").stdout.splitlines()
    if "*" in trusted or any(Path(t).expanduser() == root for t in trusted if t):
        return None
    return (
        f"{root} belongs to the account '{_account(owner)}', and git runs as "
        f"'{getpass.getuser()}': git refuses a folder another account owns. Run the "
        f"setup as '{_account(owner)}', or let git trust the folder for "
        f"'{getpass.getuser()}' — a global git setting — and run it again:\n"
        f"  git config --global --add safe.directory {root}"
    )


def _problems(root: Path, framework: Path, args: argparse.Namespace, config: dict) -> list[str]:
    """Everything that stops the setup, found before anything is changed."""
    if (root / "qf.yaml").exists():
        return ["qf.yaml already exists: this product is set up; nothing was changed."]
    untrusted = _untrusted(root)
    if untrusted:
        return [untrusted]
    if framework.resolve() != (root / FRAMEWORK_DIR).resolve():
        return [f"This framework is not the product's submodule at {FRAMEWORK_DIR}.\n{SETUP}"]
    problems = []
    if not _adopted(root) and not _origin(framework):
        problems.append(
            f"{FRAMEWORK_DIR} has no remote 'origin' to declare as the submodule's URL.\n{SETUP}"
        )
    if release_tag(framework) is None:
        problems.append(
            f"{FRAMEWORK_DIR} is not checked out at a release tag (v<major>.<minor>.<patch>); "
            f"check one out: git -C {FRAMEWORK_DIR} checkout v<version>"
        )
    for path in [*COPIED.values(), CODEOWNERS]:
        if path != FEEDBACK and (root / path).exists():
            problems.append(f"{path} already exists; the setup never overwrites a file.")
    for v in validate(config, "qf"):
        problems.append(f"qf.yaml would be invalid at {v.path or '/'}: {v.message}")
    for owner in args.code_owner:
        if not _OWNER.match(owner):
            problems.append(f"Code owner '{owner}' is not @login, @org/team or an e-mail.")
    return problems


def create_product(root: Path, args: argparse.Namespace, framework: Path) -> list[str]:
    """Set the product up from its framework clone; the problems that stopped it
    otherwise, with nothing changed."""
    config = product_config(args)
    problems = _problems(root, framework, args, config)
    if problems:
        return problems
    steps = []
    created = not (root / ".git").exists()
    if created:
        steps.append(("init", "-q"))
    if not _adopted(root):  # git adopts the clone in place: the framework stays one copy
        steps.append(("submodule", "add", "-q", _origin(framework), FRAMEWORK_DIR))
    steps.append(("add", FRAMEWORK_DIR, ".gitmodules"))  # the pin at the release
    for step in steps:
        done = _git(*step, cwd=root)
        if done.returncode != 0:
            failed = f"git {' '.join(step)} failed: {done.stderr.strip()}"
            if created:  # undo the repository this run made, so nothing was changed
                shutil.rmtree(root / ".git")
                return [failed, "The git repository this run created was removed."]
            return [failed]

    (root / "qf.yaml").write_text(
        "# Framework configuration of this product (qf.v1), written by create_product_tool.\n"
        + yaml.safe_dump(config, sort_keys=False)
    )
    for template, target in COPIED.items():
        if target == FEEDBACK and (root / target).exists():
            continue  # the product's log already holds its findings: keep them
        (root / target).parent.mkdir(parents=True, exist_ok=True)
        (root / target).write_text((framework / template).read_text())
    owners = " ".join(args.code_owner)
    (root / CODEOWNERS).write_text(
        "# A change to the gates, the framework pin or the architecture needs a person's\n"
        "# approval (SUP.1 BP1; verify_delivery_reviewed_gate); where the host supports\n"
        "# code owners, it asks them to review.\n"
        f"/{PATHS['ci_file']} {owners}\n"
        f"/.gitmodules {owners}\n"
        f"/{PATHS['architecture_dir']}/ {owners}\n"
    )
    ignore = root / ".gitignore"
    lines = ignore.read_text().splitlines() if ignore.exists() else []
    missing = [line for line in IGNORED if line not in lines]
    if missing:
        text = ignore.read_text() if ignore.exists() else ""
        if text and not text.endswith("\n"):
            text += "\n"
        ignore.write_text(
            text
            + "# The ASPICE Agent's local files and plugins: never committed.\n"
            + "".join(f"{line}\n" for line in missing)
        )
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    for flag, what in (
        ("--reviewer-agent", "a host account the reviewer agent posts from"),
        ("--urgent-approver", "a host account that may authorize an urgent fix"),
        ("--change-approver", "a host account that may approve a change request"),
        ("--code-owner", "an owner of the CI file, the framework pin and the architecture"),
    ):
        parser.add_argument(flag, action="append", required=True, help=f"{what}; repeatable")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    kept = (root / FEEDBACK).exists()

    problems = create_product(root, args, FRAMEWORK)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 2
    print(f"Set up {root} with the framework {release_tag(FRAMEWORK)} at {FRAMEWORK_DIR}.")
    if kept:
        print(f"Kept the existing {FEEDBACK} and its entries.")
    _, missing = read_config(root)
    for finding in missing:
        print(f"  {finding.rule}: {finding.message}")
    state = resolve_stage(root)
    print(f"The product is at stage {state.get('number')}, {state['stage']}: {state['status']}.")
    print(HOST_STEPS.format(framework=FRAMEWORK_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
