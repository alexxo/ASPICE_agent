"""verify_test_first_gate — SWE.4 BP1: every unit's tests came first, failed, and stayed put.

Every unit of the detailed design has a stub and a test under qf.yaml
paths.code_dir, both naming it with @unit. Over the pull request's commits,
base..HEAD (decision 9): a commit that adds or changes tests changes no existing
code — it may only add stubs (decision 10); no unit's code is committed before
its test; and every test, at the last test-only commit that added or changed
it, must fail or error there, never pass: that commit is checked out on its own
and its unit suite run, which must write its results (the red run, decisions 2
and 15). A test fixed on a retry is judged as fixed; a weakened one as
weakened. Because the commits are found in the history, not at the head, the
gate keeps holding — and keeps catching a test changed with code — at stage 6
and when the pull request re-runs every gate. Component and integration tests,
under paths.integration_tests_dir, have no stub and no red run: a commit that
changes one only must not change code (decision 1 of the integration stage);
so must software-level tests, under paths.software_tests_dir (decision 1 of
the software verification stage).

    python gates/swe/verify_test_first_gate.py [--root PRODUCT] [--base REF]
"""

from __future__ import annotations

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
    if stack is None or not units:
        return []  # the stack and detailed design gates report what is missing
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
    # on a retry replaces its earlier red run, and a weakened one is judged as weakened.
    last = {path: commit.sha for commit, changed in test_commits for path in changed}
    for commit, changed in test_commits:
        latest = [path for path in changed if last[path] == commit.sha]
        if latest:
            findings += _red_run(config, stack, commit, latest, kind)
    return findings


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


def _red_run(config: ProductConfig, stack: dict, commit: Commit, changed: list[str], kind):
    tests = [f for f in files_at(config.root, commit.sha) if kind(f) == "test"]
    key = f"commit-{commit.sha}"  # a commit never changes, so its red run is kept
    run = kept_run(config, key, "suites", "unit")
    if run is not None:
        return _judge(commit, changed, run, tests)
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
        return _judge(commit, changed, run, tests)
    finally:
        subprocess.run([*git, "worktree", "remove", "--force", str(tree)], capture_output=True)
        shutil.rmtree(work, ignore_errors=True)


def _judge(commit: Commit, changed: list[str], run, test_files: list[str]) -> list[Finding]:
    try:
        results = read_results(run.result_paths) if run.results else None
    except ResultsError:
        results = None
    if results is None:
        return [
            Finding(
                "RED_RUN_WITHOUT_RESULTS",
                changed[0],
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
        for result in mine:
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
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
