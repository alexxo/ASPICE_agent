"""Run the product's declared commands, once per tree, and keep what they produced.

The framework knows no language: it runs only the commands of the stack
(stack.v1) — the checks and the suites — each after its version_command. Two
gates need the same unit-suite run, so each command runs once per tree
(decision 13): its exit status, output, version output and the files it
wrote (JUnit XML results, Cobertura XML coverage, measurements.v1 JSON) are kept under
.qf/runs/<tree-hash>/, which git ignores. The tree hash covers HEAD, the
uncommitted changes and the untracked files, so any edit runs the command again.
Outside git nothing is kept. The red run of an older commit runs in its own
checkout and is kept under that commit's key: a commit never changes.
"""

from __future__ import annotations

import glob
import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tools.read_product_config_tool import ProductConfig
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file
from tools.validate_contract_tool import validate

__all__ = [
    "CommandRun",
    "RUNS_DIR",
    "TIMEOUT",
    "kept_run",
    "read_stack",
    "run_command",
    "tree_key",
]

RUNS_DIR = ".qf/runs"
TIMEOUT = 900  # seconds per command


@dataclass
class CommandRun:
    kind: str  # checks or suites
    name: str  # lint, format, static-analysis, unit, …
    exit_code: int  # -1 when the command timed out
    output: str
    version_exit: int
    version_output: str
    results: list[str] = field(default_factory=list)  # files kept, absolute
    coverage: str | None = None  # file kept, absolute
    measurements: list[str] = field(default_factory=list)  # files kept, absolute

    @property
    def result_paths(self) -> list[Path]:
        return [Path(p) for p in self.results]

    @property
    def measurement_paths(self) -> list[Path]:
        return [Path(p) for p in self.measurements]


def read_stack(config: ProductConfig) -> dict | None:
    """The stack when it exists and follows stack.v1; otherwise None — reporting
    a broken stack is check_stack_decision_gate's job."""
    if not config.stack_file.is_file():
        return None
    try:
        stack = read_yaml_file(config.stack_file)
    except YamlReadError:
        return None
    return None if validate(stack, "stack") else stack


def _git(root: Path, *args: str) -> str | None:
    run = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    return run.stdout.decode("utf-8", "replace") if run.returncode == 0 else None


def tree_key(root: Path) -> str | None:
    """A hash of HEAD, the uncommitted changes and the untracked files' names."""
    head = _git(root, "rev-parse", "HEAD")
    if head is None:
        return None
    diff = _git(root, "diff", "HEAD") or ""
    status = _git(root, "status", "--porcelain", "--untracked-files=all") or ""
    return hashlib.sha256("\0".join([head, diff, status]).encode()).hexdigest()[:16]


def _shell(command: str, cwd: Path) -> tuple[int, str]:
    try:
        run = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return -1, f"timed out after {TIMEOUT} s"
    return run.returncode, (run.stdout + run.stderr).strip()


def _matches(cwd: Path, pattern: str | None) -> list[Path]:
    if not pattern:
        return []
    return sorted(Path(p) for p in glob.glob(str(cwd / pattern), recursive=True))


def run_command(
    config: ProductConfig,
    kind: str,
    name: str,
    entry: dict,
    cwd: Path | None = None,
    cache: bool = True,
    key: str | None = None,
) -> CommandRun:
    """Run one declared check or suite in cwd (default: the product root), kept
    under key (default: the tree's) unless cache is False."""
    cwd = Path(cwd) if cwd is not None else config.root
    if cache and key is None:
        key = tree_key(config.root)
    store = config.root / RUNS_DIR / key if cache and key else None
    record = store / f"{kind}-{name}.json" if store else None
    kept = kept_run(config, key, kind, name) if record is not None else None
    if kept is not None:
        return kept

    written = ("results", "coverage", "measurements")
    for stale in [p for w in written for p in _matches(cwd, entry.get(w))]:
        stale.unlink(missing_ok=True)
    version_exit, version_output = _shell(entry["version_command"], cwd)
    exit_code, output = _shell(entry["run"], cwd)
    run = CommandRun(kind, name, exit_code, output, version_exit, version_output)

    results = _matches(cwd, entry.get("results"))
    coverage = _matches(cwd, entry.get("coverage"))
    measured = _matches(cwd, entry.get("measurements"))
    if store is not None:
        target = store / f"{kind}-{name}"
        target.mkdir(parents=True, exist_ok=True)
        results = [_keep(p, target / "results") for p in results]
        coverage = [_keep(p, target / "coverage") for p in coverage]
        measured = [_keep(p, target / "measurements") for p in measured]
    run.results = [str(p) for p in results]
    run.measurements = [str(p) for p in measured]
    run.coverage = str(coverage[0]) if coverage else None
    if record is not None:
        record.write_text(json.dumps(asdict(run), indent=2))
    return run


def kept_run(config: ProductConfig, key: str | None, kind: str, name: str) -> CommandRun | None:
    """The run kept under key, if there is one."""
    if not key:
        return None
    record = config.root / RUNS_DIR / key / f"{kind}-{name}.json"
    return CommandRun(**json.loads(record.read_text())) if record.is_file() else None


def _keep(path: Path, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    kept = folder / path.name
    shutil.copyfile(path, kept)
    return kept
