"""Start an independent session: the one launcher, whatever LLM runs it.

Every session apart from the orchestrator starts here — clarify (stage 2), the
tester (stage 5) and the coder (stage 6) on the author's side, the reviewer and
its three describe sessions on the person's side (tools/watch_reviews_tool.py).
No LLM is the default: each side names the command that starts its sessions in
a .env of its own, and a session may name its own:

- the author's side, in the product's .env (ignored by git):
  QF_COMMAND_TO_START_CLARIFY_SESSION, QF_COMMAND_TO_START_TESTER_SESSION,
  QF_COMMAND_TO_START_CODER_SESSION, else QF_COMMAND_TO_START_AUTHOR_SESSIONS;
- the person's side, in ~/.aspice_agent_secrets/.env, out of the author's
  reach: QF_COMMAND_TO_START_REVIEWER_SESSION,
  QF_COMMAND_TO_START_DESCRIBE_TESTS_SESSION,
  QF_COMMAND_TO_START_DESCRIBE_DESIGN_SESSION,
  QF_COMMAND_TO_START_EXPECT_CASES_SESSION, else
  QF_COMMAND_TO_START_REVIEW_SESSIONS.

A command is the agent's command line with {prompt} where the prompt goes
(e.g. codex exec --model gpt-5 {prompt}); the LLM's key sits in the same .env
under the name its CLI reads, and reaches the session's environment only. The
reviewer agent's token is never in a .env and never reaches an author session.

A session sees only what its role may read, by construction, not by
instruction. Clarify runs in a temporary folder holding the requirements, the
glossary and the diagrams. The tester runs in a temporary copy of the
committed head without a single code file — only the tests, stubs it writes,
the design, the plan and the rest — so it never sees the code, also when a
changed requirement brings stage 5 back after the code exists. Afterwards only
what the tester may write comes back to the product: test files and the
verification plan, and a stub for a unit that has no code yet, all in the
component's folder; anything else is refused and listed. The coder works in
the product itself: it must see the tests, and the gates stop it changing them.
On a retry, --findings hands the session the reviewer's findings (a file under
.qf/reviews/, which no commit holds): copied into the tester's folder, named
to the coder (FB-78). The coder runs the stack's checks and suites, so the
product's toolchain (QF_PATH_TO_PRODUCT_TOOLCHAIN in its .env) is first on its
PATH, as for every command the framework runs (FB-80).

    python tools/start_session_tool.py --session clarify --task "Check these: …" [--root PRODUCT]
    python tools/start_session_tool.py --session tester --component ID [--findings F] [--root P]
    python tools/start_session_tool.py --session coder --component ID [--findings F] [--root P]

Prints what happened as JSON: the session's output file, the files brought
back, refused and skipped. Exit 0 done, 1 the session failed or wrote what its
role may not, 2 it could not start.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.read_host_tool import HOST_TOKEN  # noqa: E402
from tools.read_product_config_tool import (  # noqa: E402
    ConfigError,
    ProductConfig,
    read_product_config,
)
from tools.run_stack_commands_tool import toolchain_env  # noqa: E402

__all__ = [
    "AUTHOR_ENV",
    "PERSON_ENV",
    "SESSIONS",
    "SessionError",
    "bring_back",
    "command_for",
    "person_env_file",
    "read_env",
    "session_env",
    "tester_copy",
]

AUTHOR_ENV = Path(".env")  # in the product
PERSON_ENV = Path(".aspice_agent_secrets") / ".env"  # in the home of whoever runs the watcher
AUTHOR_FALLBACK = "QF_COMMAND_TO_START_AUTHOR_SESSIONS"
REVIEW_FALLBACK = "QF_COMMAND_TO_START_REVIEW_SESSIONS"
SESSIONS = {  # session -> (its own setting, its side's fallback)
    "clarify": ("QF_COMMAND_TO_START_CLARIFY_SESSION", AUTHOR_FALLBACK),
    "tester": ("QF_COMMAND_TO_START_TESTER_SESSION", AUTHOR_FALLBACK),
    "coder": ("QF_COMMAND_TO_START_CODER_SESSION", AUTHOR_FALLBACK),
    "reviewer": ("QF_COMMAND_TO_START_REVIEWER_SESSION", REVIEW_FALLBACK),
    "describe_tests": ("QF_COMMAND_TO_START_DESCRIBE_TESTS_SESSION", REVIEW_FALLBACK),
    "describe_design": ("QF_COMMAND_TO_START_DESCRIBE_DESIGN_SESSION", REVIEW_FALLBACK),
    "expect_cases": ("QF_COMMAND_TO_START_EXPECT_CASES_SESSION", REVIEW_FALLBACK),
}
PROMPTS = {
    "clarify": "clarify_criteria_prompt.md",
    "tester": "write_unit_tests_prompt.md",
    "coder": "write_unit_code_prompt.md",
}
STAGES = {"tester": "unit_tests", "coder": "unit_construction"}
SECRETS = (HOST_TOKEN, "GH_TOKEN")  # never in a session the author's side starts
LOGS = Path(".qf") / "sessions"
FINDINGS = LOGS / "findings.md"  # in the tester's folder
AGENT_DIR = Path(__file__).resolve().parents[1] / "agent"


class SessionError(Exception):
    """A session that cannot start: what is missing, and where to set it."""


def person_env_file() -> Path:
    """The person's .env, in the home folder of whoever runs the watcher."""
    return Path.home() / PERSON_ENV


def read_env(path: Path) -> dict[str, str]:
    """A .env file's settings: NAME=value lines, # comments and empty lines left
    out, an optional `export `, one pair of quotes around a value removed. No
    file gives no settings."""
    path = Path(path)
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.removeprefix("export ").partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[name.strip()] = value
    return values


def command_for(session: str, values: dict[str, str], where: str):
    """The session's command — its own setting, else its side's — as prompt -> argv."""
    own, fallback = SESSIONS[session]
    template = values.get(own) or values.get(fallback)
    if not template:
        raise SessionError(
            f"No command starts the {session} session: set {fallback} (or {own}) in {where}, "
            "the agent's command line with {prompt} where the prompt goes, e.g. "
            "'codex exec {prompt}'."
        )
    parts = shlex.split(template)
    if not any("{prompt}" in part for part in parts):
        raise SessionError(f"The command for the {session} session in {where} has no {{prompt}}.")

    def command(prompt: str) -> list[str]:
        return [part.replace("{prompt}", prompt) for part in parts]

    return command


def session_env(values: dict[str, str], drop: tuple[str, ...] = SECRETS) -> dict[str, str]:
    """The session's environment: this process's, the side's .env added, the
    secrets dropped."""
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update({k: v for k, v in values.items() if k not in drop})
    return env


@dataclass
class Result:
    session: str
    output: str = ""
    returncode: int = 0
    brought: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _stack(config: ProductConfig) -> dict:
    from tools.run_stack_commands_tool import read_stack

    stack = read_stack(config)
    if stack is None:
        raise SessionError(
            f"No valid stack at {config.relative(config.stack_file)}: the tester's copy needs "
            "its code_files to leave the code out."
        )
    return stack


def _unit_test_files(config: ProductConfig) -> list[str]:
    from tools.run_stack_commands_tool import plan_suites

    return list(plan_suites(config).get("unit", {}).get("test_files", []))


def _kind(path_in_code: str, code_files: list[str], test_files: list[str]) -> str | None:
    from tools.read_unit_markers_tool import classify

    return classify(path_in_code, {"code_files": code_files, "test_files": test_files})


def _files(folder: Path) -> dict[str, str]:
    """Every file under the folder, by posix path, with a hash of its content."""
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def tester_copy(config: ProductConfig, stack: dict, into: Path) -> None:
    """The committed head, unpacked into a folder without a single code file:
    a file under paths.code_dir matching the stack's code_files and not the
    unit suite's test_files is left out. The .env is never committed, so never
    in it."""
    archive = subprocess.run(
        ["git", "-C", str(config.root), "archive", "HEAD"], capture_output=True
    )
    if archive.returncode != 0:
        raise SessionError("The product's head could not be read (git archive HEAD).")
    into.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(into, filter="data")
    code = config.relative(config.code_dir).rstrip("/") + "/"
    code_files, test_files = stack.get("code_files", []), _unit_test_files(config)
    for path in list(_files(into)):
        if path.startswith(code) and _kind(path[len(code) :], code_files, test_files) == "code":
            (into / path).unlink()


def bring_back(
    config: ProductConfig,
    copy: Path,
    before: dict[str, str],
    component: str,
    code_files: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """What the tester wrote, brought back to the product when its role may
    write it: the verification plan, and in the component's folder test files
    (by the unit suite's test_files of the plan as the tester left it) and the
    stub of a unit that has no code yet. Returns (brought, refused, skipped):
    a stub whose unit has code in the product is skipped, the code kept."""
    from tools.read_unit_markers_tool import in_component_folder

    after = _files(copy)
    test_files = _unit_test_files(read_product_config(copy))
    code = config.relative(config.code_dir).rstrip("/") + "/"
    plan = config.relative(config.verification_plan_file)
    brought: list[str] = []
    refused: list[str] = []
    skipped: list[str] = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) == after.get(path):
            continue
        inner = path[len(code) :] if path.startswith(code) else None
        kind = _kind(inner, code_files, test_files) if inner is not None else None
        target = config.root / path
        if path == plan or (
            kind == "test" and inner is not None and in_component_folder(inner, component)
        ):
            if path in after:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(copy / path, target)
            else:
                target.unlink(missing_ok=True)
            brought.append(path)
        elif kind == "code" and path in after and in_component_folder(inner, component):
            if target.exists():
                skipped.append(path)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(copy / path, target)
                brought.append(path)
        else:
            refused.append(path)
    return brought, refused, skipped


def _instructions(name: str) -> str:
    """The prompt file's instructions, from its '## You' on."""
    return "## You" + (AGENT_DIR / name).read_text(encoding="utf-8").split("## You", 1)[-1]


def _rules(root: Path, stage_id: str) -> list[Path]:
    """The stage's method and rules, as load_skills_tool names them."""
    from agent.load_skills_tool import load_skills

    try:
        loaded = load_skills(root, stage_id)
    except ValueError as err:
        raise SessionError(str(err)) from err
    files = [loaded["plugin"]["skill_file"]] if loaded["plugin"] else []
    files += [p["skill_file"] for p in loaded["also_plugins"]] + loaded["framework_skills"]
    return [Path(f) for f in files]


def _run(argv: list[str], cwd: Path, env: dict[str, str]) -> tuple[str, int]:
    try:
        done = subprocess.run(
            argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
    except OSError as err:
        return f"The agent could not be started: {err}", 127
    return done.stdout or "", done.returncode


def _retry(findings: str | None) -> str:
    """The prompt's sentence handing a retry the reviewer's findings."""
    if not findings:
        return ""
    return (
        " This is a retry: the work still follows the component's detailed design as it "
        f"stands; read the reviewer's findings in {findings} and also fix every one for this "
        "component."
    )


def _unfenced(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:]).rsplit("```", 1)[0]
    return text.strip() + "\n"


def clarify(config: ProductConfig, task: str, command, env) -> Result:
    """The clarify session, in a folder of the requirements, glossary and diagrams."""
    alone = Path(tempfile.mkdtemp(prefix="qf-clarify-"))
    try:
        for source in (config.requirements_dir, config.glossary_file, config.diagrams_dir):
            target = alone / config.relative(source)
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            elif source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        prompt = (
            f"{task}\n\nThis folder holds the requirements, the glossary and the approved "
            f"diagrams, and nothing else: read nothing outside it.\n\n"
            f"{_instructions(PROMPTS['clarify'])}"
        )
        output, code = _run(command(prompt), alone, env)
    finally:
        shutil.rmtree(alone, ignore_errors=True)
    return Result("clarify", output, code)


def tester(
    config: ProductConfig, component: str, command, env, findings: Path | None = None
) -> Result:
    """The tester session, in a copy of the head without the code; only what
    the tester may write comes back."""
    stack = _stack(config)
    rules = _rules(config.root, STAGES["tester"])
    copy = Path(tempfile.mkdtemp(prefix="qf-tester-"))
    try:
        tester_copy(config, stack, copy)
        shown = []
        for rule in rules:  # the rulebooks travel with the copy: the framework is not in it
            name = f"{rule.parent.name}.md"
            (copy / LOGS / "rules").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(rule, copy / LOGS / "rules" / name)
            shown.append((LOGS / "rules" / name).as_posix())
        if findings:
            shutil.copyfile(findings, copy / FINDINGS)
        before = _files(copy)
        prompt = (
            f"Write the unit tests of component {component}. This folder is a copy of the "
            "product without its code: read nothing outside it. Read these rules first, every "
            f"one: {' '.join(shown)}.{_retry(findings and FINDINGS.as_posix())}\n\n"
            f"{_instructions(PROMPTS['tester'])}"
        )
        output, code = _run(command(prompt), copy, env)
        before = {k: v for k, v in before.items() if not k.startswith(LOGS.as_posix() + "/")}
        for path in list(_files(copy)):
            if path.startswith(LOGS.as_posix() + "/"):
                (copy / path).unlink()
        brought, refused, skipped = bring_back(
            config, copy, before, component, stack.get("code_files", [])
        )
    finally:
        shutil.rmtree(copy, ignore_errors=True)
    return Result("tester", output, code, brought, refused, skipped)


def coder(
    config: ProductConfig, component: str, command, env, findings: Path | None = None
) -> Result:
    """The coder session, in the product: it sees the tests, and the gates keep
    them as the tester wrote them."""
    rules = " ".join(p.as_posix() for p in _rules(config.root, STAGES["coder"]))
    prompt = (
        f"Write the code of component {component} until its unit tests pass. Read these rules "
        f"first, every one: {rules}.{_retry(findings and config.relative(findings))}\n\n"
        f"{_instructions(PROMPTS['coder'])}"
    )
    output, code = _run(command(prompt), config.root, toolchain_env(config.root, env))
    return Result("coder", output, code)


def start(
    root: Path,
    session: str,
    component: str | None = None,
    task: str = "",
    findings: Path | None = None,
) -> Result:
    """Start one author-side session and keep its output under .qf/sessions/."""
    config = read_product_config(root)
    if findings is not None:
        findings = (config.root / findings).resolve()
        if not findings.is_file():
            raise SessionError(f"No findings file at {findings}.")
    values = read_env(config.root / AUTHOR_ENV)
    command = command_for(session, values, f"the product's {AUTHOR_ENV}")
    env = session_env(values)
    if session == "clarify":
        result = clarify(config, task, command, env)
    elif not component:
        raise SessionError(f"The {session} session works on one component: name it (--component).")
    elif session == "tester":
        result = tester(config, component, command, env, findings)
    else:
        result = coder(config, component, command, env, findings)
    logs = config.root / LOGS
    logs.mkdir(parents=True, exist_ok=True)
    name = session if session == "clarify" else f"{session}-{component}"
    (logs / f"{name}.log").write_text(result.output, encoding="utf-8")
    if session == "clarify":
        (logs / "clarify.yaml").write_text(_unfenced(result.output), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", required=True, choices=["clarify", "tester", "coder"])
    parser.add_argument("--component", help="the component the tester or the coder works on")
    parser.add_argument("--task", default="", help="what the clarify session checks")
    parser.add_argument(
        "--findings", type=Path, help="on a retry: the reviewer's findings for the session"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        result = start(args.root, args.session, args.component, args.task, args.findings)
    except (SessionError, ConfigError) as err:
        print(str(err), file=sys.stderr)
        return 2
    name = args.session if args.session == "clarify" else f"{args.session}-{args.component}"
    report = {
        "session": result.session,
        "exit": result.returncode,
        "log": (LOGS / f"{name}.log").as_posix(),
        "brought_back": result.brought,
        "refused": result.refused,
        "skipped": result.skipped,
    }
    if args.session == "clarify":
        report["questions"] = (LOGS / "clarify.yaml").as_posix()
    print(json.dumps(report, indent=2))
    return 0 if result.returncode == 0 and not result.refused else 1


if __name__ == "__main__":
    sys.exit(main())
