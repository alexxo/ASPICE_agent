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
glossary and the diagrams, every file named in its prompt (a session may read
files but not list a folder); its answer must be a list of questions. The
tester runs in a temporary copy of the committed head without a single code
file — only the tests, stubs it writes, the design, the plan and the rest — so
it never sees the code, also when a
changed requirement brings stage 5 back after the code exists. Afterwards only
what the tester may write comes back to the product: test files and the
verification plan, and a stub for a unit that has no code yet, all in the
component's folder; anything else is refused and listed. The coder works in
the product itself: it must see the tests, and the gates stop it changing them.
On a retry, --findings hands the session a findings file no commit holds — the
reviewer's under .qf/reviews/, the coder's report naming a test it holds
wrong (.qf/sessions/coder-<component>.log), or the gates' findings in the
component's test files as the resolver printed them: copied into the tester's
folder, named to the coder (FB-78, FB-83). The coder runs the stack's checks and suites, so the
product's toolchain (QF_PATH_TO_PRODUCT_TOOLCHAIN in its .env) is first on its
PATH, as for every command the framework runs (FB-80).

Every session carries three labels for the cost dashboard, added to
OTEL_RESOURCE_ATTRIBUTES: qf.kind (the session), qf.stage (the stage it works
for) and, on the person's side, qf.pr (the pull request). Where the side's .env
sets QF_COSTS_DIR, each session also adds its row to the ledger when it ends
(tools/write_cost_ledger_tool.py): when, the pull request or branch, stage,
kind, the program that ran it, how long, and the tokens and cost, which a
command printing Claude's result object (its --output-format json) reports.
The framework reads only that object's result, as if the command had printed
text; another command's output is read as it is, and its row has no cost.

    python tools/start_session_tool.py --session clarify --task "Check these: …" [--root PRODUCT]
    python tools/start_session_tool.py --session tester --component ID [--findings F] [--root P]
    python tools/start_session_tool.py --session coder --component ID [--findings F] [--root P]

Prints what happened as JSON: the session's output file, the files brought
back, refused and skipped, and for clarify its questions file. Exit 0 done, 1
the session failed, wrote what its role may not, or — clarify — answered with
no list of questions (problem), 2 it could not start.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.read_host_tool import HOST_TOKEN, HostError, repository  # noqa: E402
from tools.read_product_config_tool import (  # noqa: E402
    ConfigError,
    ProductConfig,
    read_product_config,
)
from tools.run_stack_commands_tool import toolchain_env  # noqa: E402
from tools.write_cost_ledger_tool import COSTS_DIR, write_row  # noqa: E402

__all__ = [
    "AUTHOR_ENV",
    "PERSON_ENV",
    "SESSIONS",
    "SessionError",
    "bring_back",
    "command_for",
    "labelled",
    "person_env_file",
    "read_env",
    "record_cost",
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
STAGES = {  # the stage each session works for: its rules, its cost
    "clarify": "requirements",
    "tester": "unit_tests",
    "coder": "unit_construction",
    "reviewer": "quality_assurance",
    "describe_tests": "quality_assurance",
    "describe_design": "quality_assurance",
    "expect_cases": "quality_assurance",
}
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


def labelled(env: dict[str, str], session: str, pr: int | None = None) -> dict[str, str]:
    """The session's environment with its cost labels added to the telemetry's."""
    labels = [f"qf.kind={session}", f"qf.stage={STAGES[session]}"]
    labels += [f"qf.pr={pr}"] if pr is not None else []
    found = env.get("OTEL_RESOURCE_ATTRIBUTES", "")
    return {**env, "OTEL_RESOURCE_ATTRIBUTES": ",".join([found, *labels] if found else labels)}


def unwrap(output: str) -> tuple[str, dict | None]:
    """The session's answer, and Claude's result object when the command printed
    one (--output-format json) as its last line; other output stays as it is."""
    lines = output.strip().splitlines()
    try:
        found = json.loads(lines[-1]) if lines else None
    except ValueError:
        found = None
    if not (isinstance(found, dict) and found.get("type") == "result"):
        return output, None
    before = "\n".join(lines[:-1])  # what the command printed besides, e.g. a warning
    answer = str(found.get("result") or "")
    return (f"{before}\n{answer}" if before else answer), found


def record_cost(
    values: dict[str, str],
    root: Path,
    session: str,
    output: str,
    *,
    llm: str,
    seconds: float,
    pr: int | None = None,
    timed_out: bool = False,
) -> str:
    """The session's answer; with QF_COSTS_DIR set, its row added to the ledger."""
    answer, found = unwrap(output)
    folder = values.get(COSTS_DIR) or os.environ.get(COSTS_DIR)
    if not folder:
        return answer
    used = list(((found or {}).get("modelUsage") or {}).items())

    def tokens(name: str) -> int | None:
        return sum(u.get(name) or 0 for _, u in used) if used else None

    row = {
        "id": uuid.uuid4().hex,
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "product": _product(root),
        "pr": pr,
        "branch": None if pr is not None else _branch(root),
        "stage": STAGES[session],
        "kind": session,
        "llm": llm,
        "model": max(used, key=lambda m: m[1].get("costUSD") or 0)[0] if used else None,
        "input_tokens": tokens("inputTokens"),
        "output_tokens": tokens("outputTokens"),
        "cache_read_tokens": tokens("cacheReadInputTokens"),
        "cache_creation_tokens": tokens("cacheCreationInputTokens"),
        "seconds": round(seconds, 1),
        "cost_usd": (found or {}).get("total_cost_usd"),
        "timed_out": int(timed_out),
    }
    try:
        write_row(Path(folder), row)
    except (OSError, sqlite3.Error) as err:  # the cost is not worth a lost session
        print(f"The session's cost was not recorded in {folder}: {err}", file=sys.stderr)
    return answer


def _branch(root: Path) -> str | None:
    where = ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"]
    done = subprocess.run(where, capture_output=True, text=True)
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def _product(root: Path) -> str:
    """The ledger's name: the product's repository name, else its folder's."""
    try:
        return repository(root).split("/")[-1]
    except HostError:
        return root.resolve().name


@dataclass
class Result:
    session: str
    output: str = ""
    returncode: int = 0
    brought: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    problem: str = ""  # why the session's answer cannot be used, though it ran


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
    """The prompt's sentence handing a retry its findings, whoever wrote them."""
    if not findings:
        return ""
    return (
        " This is a retry: the work still follows the component's detailed design as it "
        f"stands; read the findings in {findings} — the reviewer's, the coder's or the gates' — "
        "and also fix every one for this component."
    )


def _unfenced(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:]).rsplit("```", 1)[0]
    return text.strip() + "\n"


def _no_questions(answer: str) -> str:
    """Why the clarify session's answer is no list of questions; empty when it is
    one (none at all included). FB-93: a session that found no file answered in
    prose, and the run looked done."""
    import yaml

    try:
        questions = yaml.safe_load(answer)
    except yaml.YAMLError as err:
        return f"the session's answer is no list of questions: it is not YAML ({err})"
    if not isinstance(questions, list) or not all(isinstance(q, dict) for q in questions):
        return (
            "the session's answer is no list of questions; read it in "
            f"{(LOGS / 'clarify.yaml').as_posix()} and start the session again"
        )
    return ""


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
        files = sorted(p.relative_to(alone).as_posix() for p in alone.rglob("*") if p.is_file())
        prompt = (  # every file named: a session may read files but not list a folder (FB-93)
            f"{task}\n\nThe requirements, the glossary and the approved diagrams are these "
            f"files, which are all this folder holds: {' '.join(files)}. Read nothing "
            f"outside it.\n\n{_instructions(PROMPTS['clarify'])}"
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
    env = labelled(session_env(values), session)
    began = time.monotonic()
    if session == "clarify":
        result = clarify(config, task, command, env)
    elif not component:
        raise SessionError(f"The {session} session works on one component: name it (--component).")
    elif session == "tester":
        result = tester(config, component, command, env, findings)
    else:
        result = coder(config, component, command, env, findings)
    llm = Path(command("")[0]).name
    seconds = time.monotonic() - began
    result.output = record_cost(
        values, config.root, session, result.output, llm=llm, seconds=seconds
    )
    logs = config.root / LOGS
    logs.mkdir(parents=True, exist_ok=True)
    name = session if session == "clarify" else f"{session}-{component}"
    (logs / f"{name}.log").write_text(result.output, encoding="utf-8")
    if session == "clarify":
        (logs / "clarify.yaml").write_text(_unfenced(result.output), encoding="utf-8")
        if result.returncode == 0:
            result.problem = _no_questions(_unfenced(result.output))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", required=True, choices=["clarify", "tester", "coder"])
    parser.add_argument("--component", help="the component the tester or the coder works on")
    parser.add_argument("--task", default="", help="what the clarify session checks")
    parser.add_argument(
        "--findings",
        type=Path,
        help="on a retry: the findings for the session — the reviewer's, the coder's, the gates'",
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
    if result.problem:
        report["problem"] = result.problem
    print(json.dumps(report, indent=2))
    return 0 if result.returncode == 0 and not result.refused and not result.problem else 1


if __name__ == "__main__":
    sys.exit(main())
