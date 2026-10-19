"""tools/read_commit_range_tool.py — the pull request's commits and their files."""

import subprocess

from product_builder import build_python_product, commit_all

from tools.read_commit_range_tool import commits, file_at, resolve_base, uncommitted


def _head(root, ref="HEAD"):
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", ref], capture_output=True, text=True, check=True
    ).stdout.strip()


def test_the_base_is_the_merge_base_with_main(tmp_path, monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)
    root = build_python_product(tmp_path)
    assert resolve_base(root) == _head(root, "main")


def test_without_a_local_main_the_base_is_the_remotes(tmp_path, monkeypatch):
    """A CI checkout of a review event has origin/main, no main and no QF_BASE (FB-28)."""
    monkeypatch.delenv("QF_BASE", raising=False)
    root = build_python_product(tmp_path)
    main = _head(root, "main")
    git = ["git", "-C", str(root)]
    subprocess.run([*git, "update-ref", "refs/remotes/origin/main", main], check=True)
    subprocess.run([*git, "checkout", "-q", "--detach"], check=True)
    subprocess.run([*git, "branch", "-q", "-D", "main"], check=True)
    (root / "a.txt").write_text("a")
    commit_all(root, "feat: a REQ-0001")
    assert resolve_base(root) == main


def test_qf_base_and_an_explicit_base_win(tmp_path, monkeypatch):
    root = build_python_product(tmp_path)
    (root / "a.txt").write_text("a")
    commit_all(root, "one")
    first = _head(root)
    (root / "b.txt").write_text("b")
    commit_all(root, "two")
    monkeypatch.setenv("QF_BASE", first)
    assert resolve_base(root) == first
    assert resolve_base(root, _head(root, "main")) == _head(root, "main")


def test_only_the_branch_commits_are_read_with_their_changes(tmp_path, monkeypatch):
    monkeypatch.delenv("QF_BASE", raising=False)
    root = build_python_product(tmp_path)
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x = 1\n")
    commit_all(root, "add")
    (root / "src" / "a.py").write_text("x = 2\n")
    commit_all(root, "change")
    found = commits(root, resolve_base(root))
    assert [[(c.status, c.path) for c in commit.changes] for commit in found] == [
        [("A", "src/a.py")],
        [("M", "src/a.py")],
    ]
    assert file_at(root, found[0].sha, "src/a.py") == "x = 1\n"
    assert file_at(root, found[0].sha, "missing.py") is None


def test_uncommitted_files_are_listed(tmp_path):
    root = build_python_product(tmp_path)
    (root / "src").mkdir()
    (root / "src" / "new.py").write_text("x = 1\n")
    assert uncommitted(root) == ["src/new.py"]
