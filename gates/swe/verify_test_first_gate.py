"""verify_test_first_gate — SWE.4 BP1: every unit's tests came first, failed, and stayed put.

Every unit of the detailed design has a stub and a test under qf.yaml
paths.code_dir, both naming it with @unit. Over the pull request's commits,
base..HEAD (decision 9): a commit that adds or changes tests changes no
existing code — it may only add stubs (decision 10); no unit's code is
committed before its test; and every test, at the last test-only commit that
added or changed it, must fail or error there, never pass: that commit is
checked out on its own and its unit suite run, which must write its results
(the red run, decisions 2 and 15). A test fixed on a retry is judged as fixed;
a weakened one as weakened. The gate judges tests, not files: a commit that
adds or changes one test of a built unit's file judges that test alone, since
the file's other tests pass on the code they already have. A test is found in
its file by its name, and its lines run to the next test, its annotations and
the comments right above it included. It changed when the commit changed code
among its lines; blank lines, comments and docstrings change nothing, and a
test removed between two others changes neither (FB-52). Code changed before
the first test (imports, fixtures, helpers) judges no test by itself, but one
of the file's tests must fail on that commit. A test whose name is not found
in its file is judged at the file's last test-only commit. Because the commits
are found in the history, not at the head, the gate keeps holding — and keeps
catching a test changed with code — at stage 6 and when the pull request
re-runs every gate. Component and integration tests, under
paths.integration_tests_dir, have no stub and no red run: a commit that changes
one only must not change code (decision 1 of the integration stage); so must
software-level tests, under paths.software_tests_dir (decision 1 of the
software verification stage).

    python gates/swe/verify_test_first_gate.py [--root PRODUCT] [--base REF]
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.check_approval_order_tool import in_git  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_commit_range_tool import (  # noqa: E402
    Commit,
    commits,
    file_at,
    files_at,
    resolve_base,
    uncommitted,
)
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_test_results_tool import ResultsError, map_to_file, read_results  # noqa: E402
from tools.read_unit_markers_tool import (  # noqa: E402
    classify,
    design_units,
    glob_match,
    markers,
    scan_sources,
)
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import kept_run, read_stack, run_command  # noqa: E402

GATE = "verify_test_first_gate"


def check(config: ProductConfig, base: str | None = None) -> list[Finding]:
    stack = read_stack(config)
    units = design_units(config)
    if stack is None or "unit" not in stack["suites"] or not units:
        return []  # the stack, plan and detailed design gates report what is missing
    findings = _present(units, scan_sources(config, stack))
    if not in_git(config.root):
        return [
            *findings,
            Finding(
                "NOT_A_GIT_REPOSITORY",
                ".",
                None,
                "The product is not a git repository, so the order of tests and code "
                "cannot be shown.",
            ),
        ]
    kind = _classifier(config, stack)
    for path in uncommitted(config.root):
        if kind(path) in ("test", "integration", "software"):
            findings.append(
                Finding(
                    "TEST_NOT_COMMITTED",
                    path,
                    None,
                    "This test is not committed; tests arrive in a test-only commit.",
                )
            )
    base_sha = resolve_base(config.root, base)
    history = commits(config.root, base_sha)
    tested_before = _units_tested_at(config.root, base_sha, kind) if base_sha else set()
    first_test: dict[str, int] = {}
    first_code: dict[str, int] = {}
    test_commits: list[tuple[Commit, list[str]]] = []
    for i, commit in enumerate(history):
        tests = [c for c in commit.changes if c.status in "AMR" and kind(c.path) == "test"]
        added = [c for c in commit.changes if c.status == "A" and kind(c.path) == "code"]
        changed = [c for c in commit.changes if c.status in "MR" and kind(c.path) == "code"]
        assembled = [
            c
            for c in commit.changes
            if c.status in "AMR" and kind(c.path) in ("integration", "software")
        ]
        if assembled and (added or changed):
            code = [*changed, *added]
            findings.append(
                Finding(
                    "TEST_CHANGED_WITH_CODE",
                    code[0].path,
                    None,
                    f"Commit {commit.short} changes component, integration or software-level "
                    f"tests ({', '.join(c.path for c in assembled)}) and also code "
                    f"({', '.join(c.path for c in code)}); the assembler's and the bridge "
                    "tester's tests come in a test-only commit, and the coder never changes "
                    "them.",
                )
            )
        for c in tests:
            for unit in _units_in(config.root, commit.sha, c.path):
                first_test.setdefault(unit, i)
        for c in [*added, *changed]:
            for unit in _units_in(config.root, commit.sha, c.path):
                first_code.setdefault(unit, i)
        if not tests:
            continue
        if changed:
            rule = (
                "CODE_IN_TEST_COMMIT"
                if any(c.status == "A" for c in tests)
                else "TEST_CHANGED_WITH_CODE"
            )
            findings.append(
                Finding(
                    rule,
                    changed[0].path,
                    None,
                    f"Commit {commit.short} changes tests and also changes code "
                    f"({', '.join(c.path for c in changed)}); tests come in a test-only "
                    "commit, which may only add stubs, and code in another.",
                )
            )
        else:
            test_commits.append((commit, [c.path for c in tests]))
    for unit, at in sorted(first_code.items()):
        if unit in tested_before or unit not in units:
            continue
        if unit not in first_test or at < first_test[unit]:
            findings.append(
                Finding(
                    "CODE_BEFORE_TEST",
                    units[unit][1],
                    None,
                    f"The code of {unit} was committed in {history[at].short}, before its "
                    "test; a unit's test comes first.",
                )
            )
    # A test is judged at the last test-only commit that changed it: a test fixed
    # on a retry replaces its earlier red run, a weakened one is judged as weakened,
    # and a test the commit left as it was is not judged there (FB-51).
    findings += _judge_tests(config, stack, test_commits, kind)
    return findings


def _judge_tests(config: ProductConfig, stack: dict, test_commits: list, kind) -> list[Finding]:
    touched: dict[str, list[Commit]] = {}
    for commit, changed in test_commits:
        for path in changed:
            touched.setdefault(path, []).append(commit)
    runs: dict[str, tuple] = {}

    def red(commit: Commit) -> tuple:
        if commit.sha not in runs:
            runs[commit.sha] = _red_run(config, stack, commit, kind)
        return runs[commit.sha]

    wanted: dict[str, dict[str, set[str] | None]] = {}  # commit -> file -> tests (None: all)
    fixtures: dict[str, set[str]] = {}  # commit -> files whose code before the tests changed
    for path, touching in touched.items():
        latest = touching[-1]
        names = _names(*red(latest), path)
        if not names:  # no results, or none for this file: the red run's finding says so
            wanted.setdefault(latest.sha, {})[path] = None
            continue
        changes = {c.sha: _changed_tests(config.root, c, path, names) for c in touching}
        for c in touching:
            if changes[c.sha][1]:
                fixtures.setdefault(c.sha, set()).add(path)
                wanted.setdefault(c.sha, {}).setdefault(path, set())
        for name in sorted(names):
            if name in changes[latest.sha][2]:  # not found in the file: judged at its latest
                wanted.setdefault(latest.sha, {}).setdefault(path, set()).add(name)
                continue
            at = next((c for c in reversed(touching) if name in changes[c.sha][0]), None)
            if at is not None:  # None: older than the pull request, judged before
                wanted.setdefault(at.sha, {}).setdefault(path, set()).add(name)
    findings = []
    for commit, _ in test_commits:
        if commit.sha in wanted:
            findings += _judge(commit, wanted[commit.sha], *red(commit), fixtures.get(commit.sha))
    return findings


def _base_name(result) -> str:
    """A result's test name without its parameters: test_x[1] and testX() are test_x, testX."""
    return re.split(r"[\[(]", result.name, maxsplit=1)[0]


def _names(run, test_files: list[str], path: str) -> set[str] | None:
    """The names of a test file's tests in a red run, or None without results."""
    try:
        results = read_results(run.result_paths) if run.results else None
    except ResultsError:
        results = None
    if results is None:
        return None
    return {_base_name(r) for r in results if map_to_file(r, test_files) == path}


PROSE = re.compile(r"^\s*($|#|//|/\*|\*)")  # blank or comment lines
LEADING = re.compile(r"^\s*(@|#|//|/\*|\*)")  # annotations and comments above a test


def _python_parts(path: str, text: str) -> tuple[set[int], dict[int, int]]:
    """A Python file's docstring lines, and each function's first decorator line by
    its def line (0-based); nothing for another language or a file that does not parse."""
    if not path.endswith(".py"):
        return set(), {}
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return set(), {}
    docs: set[int] = set()
    decorated: dict[int, int] = {}
    for node in ast.walk(tree):
        defined = isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        if defined and node.decorator_list:
            decorated[node.lineno - 1] = min(d.lineno for d in node.decorator_list) - 1
        if defined or isinstance(node, ast.Module):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docs.update(range(first.lineno - 1, first.end_lineno))
    return docs, decorated


def _prose(path: str, text: str) -> set[int]:
    """The lines that change no behaviour: blank lines, comments and docstrings."""
    docs, _ = _python_parts(path, text)
    return docs | {i for i, line in enumerate(text.splitlines()) if PROSE.match(line)}


def _starts(path: str, text: str, names: set[str]) -> tuple[dict[str, int], set[str]]:
    """Each found test's first line — its annotations and the comments right above it
    included — and the names not found. A test's lines run to the next test's first
    line; the lines before the first test hold the imports, fixtures and helpers."""
    lines = text.splitlines()
    _, decorated = _python_parts(path, text)
    starts = {}
    for name in names:
        word = re.compile(rf"\b{re.escape(name)}\b")
        found = next((i for i, line in enumerate(lines) if word.search(line)), None)
        if found is None:
            continue
        found = decorated.get(found, found)
        while found > 0 and lines[found - 1].strip() and LEADING.match(lines[found - 1]):
            found -= 1
        starts[name] = found
    return starts, set(names) - set(starts)


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)


def _hunks(root: Path, commit: Commit, path: str) -> list[tuple[int, int, int, int]]:
    """The commit's changed line ranges in a file: old start, count, new start, count."""
    diff = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "-U0",
            "--no-color",
            "--no-ext-diff",
            f"{commit.sha}^",
            commit.sha,
            "--",
            path,
        ],
        capture_output=True,
        text=True,
    ).stdout
    return [
        (int(a), int(b) if b else 1, int(c), int(d) if d else 1)
        for a, b, c, d in HUNK.findall(diff)
    ]


def _changed_tests(root: Path, commit: Commit, path: str, names: set[str]):
    """The tests whose own code a commit added or changed in a file; whether it changed
    code before the first test (imports, fixtures, helpers); and the names not found.
    Blank lines, comments and docstrings change nothing, and a test removed between
    two others changes neither (FB-52)."""
    text = file_at(root, commit.sha, path) or ""
    starts, missing = _starts(path, text, names)
    before = file_at(root, f"{commit.sha}^", path)
    if before is None:
        return set(starts), False, missing
    lines = text.splitlines()
    order = sorted(starts.items(), key=lambda item: item[1])
    new_prose, old_prose = _prose(path, text), _prose(path, before)

    def owner(i: int) -> str:  # "" for the lines before the first test
        return next((name for name, start in reversed(order) if start <= i), "")

    owners: set[str] = set()
    for old_at, old_count, new_at, new_count in _hunks(root, commit, path):
        new = range(new_at - 1, new_at - 1 + new_count)
        owners |= {owner(i) for i in new if i not in new_prose}
        if all(i in old_prose for i in range(old_at - 1, old_at - 1 + old_count)):
            continue
        if any(i not in new_prose for i in new):
            continue  # code replaced: owned by the replacing lines, above
        last = new_at - 2 if new_count else new_at - 1  # code removed after this line
        nxt = next((i for i in range(last + 1, len(lines)) if i not in new_prose), None)
        if nxt is not None and (owner(last) if last >= 0 else "") == owner(nxt):
            owners.add(owner(nxt))  # inside one test, or before the first: not between two
    return owners - {""}, "" in owners, missing


def _present(units: dict, sources: list) -> list[Finding]:
    stubbed = {u for s in sources if s.kind == "code" for u in s.units}
    tested = {u for s in sources if s.kind == "test" for u in s.units}
    findings = []
    for unit, (component, design) in sorted(units.items()):
        if unit not in stubbed:
            findings.append(
                Finding(
                    "MISSING_STUB",
                    design,
                    None,
                    f"Unit {unit} of {component} has no stub or code file naming it.",
                )
            )
        if unit not in tested:
            findings.append(
                Finding(
                    "MISSING_UNIT_TEST",
                    design,
                    None,
                    f"Unit {unit} of {component} has no unit test naming it.",
                )
            )
    return findings


def _prefix(config: ProductConfig, folder: Path) -> str:
    inner = config.relative(folder)
    return "" if inner in ("", ".") else inner.rstrip("/") + "/"


def _classifier(config: ProductConfig, stack: dict):
    prefix = _prefix(config, config.code_dir)
    assembly = _prefix(config, config.integration_tests_dir)
    ground = _prefix(config, config.software_tests_dir)

    def kind(path: str) -> str | None:
        if path.startswith(ground) and glob_match(
            path[len(ground) :], stack.get("software_test_files", [])
        ):
            return "software"
        if path.startswith(assembly) and glob_match(
            path[len(assembly) :], stack.get("integration_test_files", [])
        ):
            return "integration"
        if not path.startswith(prefix):
            return None
        return classify(path[len(prefix) :], stack)

    return kind


def _units_in(root: Path, rev: str, path: str) -> set[str]:
    text = file_at(root, rev, path)
    return set(markers(text)[0]) if text is not None else set()


def _units_tested_at(root: Path, rev: str, kind) -> set[str]:
    return {u for f in files_at(root, rev) if kind(f) == "test" for u in _units_in(root, rev, f)}


def _red_run(config: ProductConfig, stack: dict, commit: Commit, kind) -> tuple:
    """A commit's red run, and its test files."""
    tests = [f for f in files_at(config.root, commit.sha) if kind(f) == "test"]
    key = f"commit-{commit.sha}"  # a commit never changes, so its red run is kept
    run = kept_run(config, key, "suites", "unit")
    if run is not None:
        return run, tests
    work = Path(tempfile.mkdtemp(prefix="qf-red-run-"))
    tree = work / "tree"
    git = ["git", "-C", str(config.root)]
    try:
        subprocess.run(
            [*git, "worktree", "add", "--detach", "-q", str(tree), commit.sha],
            capture_output=True,
            check=True,
        )
        entry = stack["suites"]["unit"]
        run = run_command(config, "suites", "unit", entry, cwd=tree, key=key)
        return run, tests
    finally:
        subprocess.run([*git, "worktree", "remove", "--force", str(tree)], capture_output=True)
        shutil.rmtree(work, ignore_errors=True)


def _judge(
    commit: Commit,
    changed: dict[str, set[str] | None],
    run,
    test_files: list[str],
    fixtures: set[str] | None = None,
) -> list[Finding]:
    """The red run's findings for the tests the commit added or changed, by file; a file
    whose code before its tests changed needs one of its tests to fail there."""
    try:
        results = read_results(run.result_paths) if run.results else None
    except ResultsError:
        results = None
    if results is None:
        return [
            Finding(
                "RED_RUN_WITHOUT_RESULTS",
                next(iter(changed)),
                None,
                f"On commit {commit.short} the unit suite exited {run.exit_code} and wrote no "
                "results — the tests and stubs must compile and run there.",
            )
        ]
    by_file: dict[str, list] = {}
    for result in results:
        file = map_to_file(result, test_files)
        if file is not None:
            by_file.setdefault(file, []).append(result)
    findings = []
    for file in changed:
        mine = by_file.get(file, [])
        if not mine:
            findings.append(
                Finding(
                    "RED_RUN_WITHOUT_RESULTS",
                    file,
                    None,
                    f"On commit {commit.short} no result belongs to this test file.",
                )
            )
        only = changed[file]
        for result in mine:
            if only is not None and _base_name(result) not in only:
                continue  # left as it was: judged at the commit that last changed it
            if result.outcome == "passed":
                findings.append(
                    Finding(
                        "TEST_NOT_FAILING",
                        file,
                        None,
                        f"{result.label} passes on commit {commit.short}, before its code "
                        "exists; a test that passes against a stub tests nothing.",
                    )
                )
        red = any(r.outcome in ("failed", "error") for r in mine)
        if file in (fixtures or ()) and mine and not red:
            findings.append(
                Finding(
                    "TEST_NOT_FAILING",
                    file,
                    None,
                    f"Commit {commit.short} changes this file's code before its tests "
                    "(imports, fixtures, helpers), and no test of the file fails there; "
                    "such a change comes with a test that fails on it.",
                )
            )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
