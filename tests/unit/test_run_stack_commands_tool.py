"""tools/run_stack_commands_tool.py — declared commands run once per tree."""

import shlex
import sys

from product_builder import build_python_product

from tools.read_product_config_tool import read_product_config
from tools.run_stack_commands_tool import read_stack, run_command, tree_key

PY = shlex.quote(sys.executable)


def _counting_entry(root):
    """A suite that counts its own runs and writes a results file."""
    script = (
        "import pathlib;p=pathlib.Path('runs.txt');p.write_text(p.read_text()+'x' "
        "if p.exists() else 'x');pathlib.Path('build').mkdir(exist_ok=True);"
        "pathlib.Path('build/r.xml').write_text('<testsuites/>')"
    )
    return {
        "run": f'{PY} -c "{script}"',
        "tool": "python",
        "version": "1",
        "version_command": "echo python 1",
        "results": "build/r.xml",
    }


def test_a_command_runs_once_per_tree(tmp_path):
    root = build_python_product(tmp_path)
    (root / ".gitignore").write_text((root / ".gitignore").read_text() + "runs.txt\n")
    config = read_product_config(root)
    entry = _counting_entry(root)
    first = run_command(config, "suites", "unit", entry)
    second = run_command(config, "suites", "unit", entry)
    assert (root / "runs.txt").read_text() == "x"
    assert first == second
    assert first.version_output == "python 1"
    assert first.result_paths[0].read_text() == "<testsuites/>"
    assert ".qf/runs/" in first.results[0]


def test_any_edit_runs_it_again(tmp_path):
    root = build_python_product(tmp_path)
    (root / ".gitignore").write_text((root / ".gitignore").read_text() + "runs.txt\n")
    config = read_product_config(root)
    entry = _counting_entry(root)
    before = tree_key(root)
    run_command(config, "suites", "unit", entry)
    (root / "docs" / "glossary.md").write_text("changed")
    assert tree_key(root) != before
    run_command(config, "suites", "unit", entry)
    assert (root / "runs.txt").read_text() == "xx"


def test_without_the_cache_nothing_is_kept_and_stale_results_go(tmp_path):
    root = build_python_product(tmp_path)
    config = read_product_config(root)
    (root / "build").mkdir()
    (root / "build" / "r.xml").write_text("stale")
    entry = {
        "run": "true",
        "tool": "sh",
        "version": "1",
        "version_command": "true",
        "results": "build/r.xml",
    }
    run = run_command(config, "suites", "unit", entry, cache=False)
    assert run.results == []
    assert not (root / ".qf" / "runs").exists()


def test_a_missing_or_broken_stack_reads_as_none(tmp_path):
    root = build_python_product(tmp_path)
    config = read_product_config(root)
    assert read_stack(config)["contract"] == "stack.v1"
    config.stack_file.write_text("contract: stack.v1\n")
    assert read_stack(config) is None
    config.stack_file.unlink()
    assert read_stack(config) is None


def test_a_run_can_be_kept_under_its_own_key(tmp_path):
    from tools.run_stack_commands_tool import kept_run

    root = build_python_product(tmp_path)
    (root / ".gitignore").write_text((root / ".gitignore").read_text() + "runs.txt\n")
    config = read_product_config(root)
    entry = _counting_entry(root)
    assert kept_run(config, "commit-abc", "suites", "unit") is None
    run_command(config, "suites", "unit", entry, key="commit-abc")
    (root / "docs" / "glossary.md").write_text("changed")  # another tree, same key
    run_command(config, "suites", "unit", entry, key="commit-abc")
    assert (root / "runs.txt").read_text() == "x"
    assert kept_run(config, "commit-abc", "suites", "unit") is not None


def test_measurements_are_kept_with_the_run_and_stale_ones_go(tmp_path):
    root = build_python_product(tmp_path)
    config = read_product_config(root)
    script = (
        "import pathlib;d=pathlib.Path('build/m');d.mkdir(parents=True,exist_ok=True);"
        "(d/'bench.json').write_text('{}')"
    )
    entry = {
        "run": f'{PY} -c "{script}"',
        "tool": "python",
        "version": "1",
        "version_command": "echo python 1",
        "results": "build/r.xml",
        "measurements": "build/m/*.json",
    }
    (root / "build" / "m").mkdir(parents=True)
    (root / "build" / "m" / "old.json").write_text("{}")
    run = run_command(config, "suites", "bench", entry, cache=False)
    assert [p.name for p in run.measurement_paths] == ["bench.json"]
    kept = run_command(config, "suites", "bench", entry)
    assert ".qf/runs/" in kept.measurements[0]
