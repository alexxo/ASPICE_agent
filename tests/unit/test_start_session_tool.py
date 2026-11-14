"""tools/start_session_tool.py — any LLM, and a session sees only what its role may read."""

import json
import shlex
import sys
from pathlib import Path

import pytest
from product_builder import (
    QF,
    build_python_product,
    commit_all,
    install_plugins,
    write_all_code,
    write_all_tests_and_stubs,
)

from tools import start_session_tool
from tools.start_session_tool import SessionError, command_for, read_env, session_env


def test_a_env_file_is_read_as_names_and_values(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# the author's sessions\n\n"
        "QF_COMMAND_TO_START_AUTHOR_SESSIONS=claude -p {prompt}\n"
        "export OPENAI_API_KEY='sk-test'\n"
        'QUOTED="a b"\n'
        "not a setting\n"
    )
    assert read_env(env) == {
        "QF_COMMAND_TO_START_AUTHOR_SESSIONS": "claude -p {prompt}",
        "OPENAI_API_KEY": "sk-test",
        "QUOTED": "a b",
    }
    assert read_env(tmp_path / "missing.env") == {}


def test_a_session_takes_its_own_command_else_its_sides():
    values = {
        "QF_COMMAND_TO_START_AUTHOR_SESSIONS": "claude -p {prompt}",
        "QF_COMMAND_TO_START_TESTER_SESSION": "codex exec --model gpt-5 {prompt}",
    }
    prompt = "Write the 'tests' of component auth-service"
    tester = command_for("tester", values, ".env")(prompt)
    assert tester == ["codex", "exec", "--model", "gpt-5", prompt]  # one argument, quotes kept
    assert command_for("coder", values, ".env")("go") == ["claude", "-p", "go"]


def test_no_llm_is_the_default():
    with pytest.raises(SessionError) as err:
        command_for("clarify", {}, "the product's .env")
    said = str(err.value)
    assert "QF_COMMAND_TO_START_AUTHOR_SESSIONS" in said and "the product's .env" in said
    with pytest.raises(SessionError, match="no {prompt}"):
        command_for("reviewer", {"QF_COMMAND_TO_START_REVIEW_SESSIONS": "gemini"}, "~/.env")


def test_the_keys_reach_the_session_and_the_tokens_never_do(monkeypatch):
    monkeypatch.setenv("QF_HOST_TOKEN", "reviewer-token")
    monkeypatch.setenv("GH_TOKEN", "gh-token")
    env = session_env({"OPENAI_API_KEY": "sk-test", "QF_HOST_TOKEN": "in-the-env-file"})
    assert env["OPENAI_API_KEY"] == "sk-test"
    assert "QF_HOST_TOKEN" not in env and "GH_TOKEN" not in env


# ── the sessions, played by a script standing in for the LLM ────────────────

PYTHON = shlex.quote(sys.executable)

TESTER = """
import os, pathlib, sys
prompt = sys.argv[1]
files = sorted(p.as_posix() for p in pathlib.Path('.').rglob('*') if p.is_file())
code = [f for f in files if f.startswith('src/') and not pathlib.Path(f).name.startswith('test_')]
assert not code, code  # no code file, also where the code exists
assert 'src/auth_service/test_check_credentials.py' in files  # the tests are there
assert '.env' not in files
assert 'QF_HOST_TOKEN' not in os.environ and os.environ['OPENAI_API_KEY'] == 'sk-test'
assert 'component auth-service' in prompt
rules = [w.rstrip('.') for w in prompt.split() if w.startswith('.qf/sessions/rules/')]
assert len(rules) == 4 and all(pathlib.Path(r).is_file() for r in rules), rules
pathlib.Path('src/auth_service/test_lock_account.py').write_text('# @unit[lock-account]\\n')
pathlib.Path('src/auth_service/lock_account.py').write_text('# @unit[lock-account]\\n')
pathlib.Path('src/auth_service/check_credentials.py').write_text('# a stub over the code\\n')
pathlib.Path('src/auth_service/test_open_session.py').unlink()
pathlib.Path('src/web_app/test_other.py').write_text('# another component\\n')
pathlib.Path('README.md').write_text('changed')
print('tests written')
"""


@pytest.fixture
def built(tmp_path):
    """A product with its code and tests committed: stage 5 comes back after the code."""
    root = build_python_product(tmp_path / "product")
    install_plugins(root)
    write_all_tests_and_stubs(root)
    write_all_code(root)
    (root / ".gitignore").write_text((root / ".gitignore").read_text() + ".env\n")
    commit_all(root, "feat: the units REQ-0047")
    return root


def _session(root, tmp_path, script, monkeypatch):
    (tmp_path / "llm.py").write_text(script)
    (root / ".env").write_text(
        f"QF_COMMAND_TO_START_AUTHOR_SESSIONS={PYTHON} {tmp_path / 'llm.py'} {{prompt}}\n"
        "OPENAI_API_KEY=sk-test\n"
    )
    monkeypatch.setenv("QF_HOST_TOKEN", "reviewer-token")


def test_the_tester_never_sees_the_code_and_only_its_files_come_back(
    built, tmp_path, monkeypatch, capsys
):
    _session(built, tmp_path, TESTER, monkeypatch)
    code_before = (built / "src/auth_service/check_credentials.py").read_text()
    args = ["--session", "tester", "--component", "auth-service", "--root", str(built)]
    assert start_session_tool.main(args) == 1  # it wrote what its role may not
    report = json.loads(capsys.readouterr().out)
    assert report["brought_back"] == [
        "src/auth_service/lock_account.py",  # the stub of a new unit
        "src/auth_service/test_lock_account.py",
        "src/auth_service/test_open_session.py",  # a retired test, removed
    ]
    assert report["refused"] == ["README.md", "src/web_app/test_other.py"]
    assert report["skipped"] == ["src/auth_service/check_credentials.py"]
    assert (built / "src/auth_service/check_credentials.py").read_text() == code_before
    assert (built / "src/auth_service/lock_account.py").is_file()
    assert not (built / "src/auth_service/test_open_session.py").exists()
    assert not (built / "src/web_app/test_other.py").exists()
    assert "tests written" in (built / ".qf/sessions/tester-auth-service.log").read_text()


def test_a_tester_writing_only_its_files_ends_clean(built, tmp_path, monkeypatch, capsys):
    clean = TESTER.split("pathlib.Path('src/auth_service/check_credentials.py')")[0]
    _session(built, tmp_path, clean + "print('tests written')\n", monkeypatch)
    args = ["--session", "tester", "--component", "auth-service", "--root", str(built)]
    assert start_session_tool.main(args) == 0
    assert json.loads(capsys.readouterr().out)["refused"] == []


CLARIFIER = """
import pathlib, sys
allowed = sys.argv[2:]
files = sorted(p.as_posix() for p in pathlib.Path('.').rglob('*') if p.is_file())
assert files and all(any(f.startswith(a) for a in allowed) for f in files), files
assert sys.argv[1].startswith('Check these: REQ-0047 criterion 1')
print('```yaml')
print('- question: What is a failed attempt?')
print('```')
"""


def test_clarify_sees_the_requirements_glossary_and_diagrams_only(
    built, tmp_path, monkeypatch, capsys
):
    paths = QF["paths"]
    allowed = " ".join(paths[k] for k in ("requirements_dir", "glossary_file", "diagrams_dir"))
    _session(built, tmp_path, CLARIFIER, monkeypatch)
    env = (built / ".env").read_text().replace("{prompt}", "{prompt} " + allowed)
    (built / ".env").write_text(env)
    args = ["--session", "clarify", "--task", "Check these: REQ-0047 criterion 1"]
    assert start_session_tool.main([*args, "--root", str(built)]) == 0
    report = json.loads(capsys.readouterr().out)
    questions = built / report["questions"]
    assert questions.read_text() == "- question: What is a failed attempt?\n"


CODER = """
import pathlib, sys
assert pathlib.Path.cwd().resolve() == pathlib.Path(sys.argv[2]).resolve()
prompt = sys.argv[1]
assert 'component web-app' in prompt and 'derive_unit_code_plugin/SKILL.md' in prompt
print('code written')
"""


def test_the_coder_works_in_the_product(built, tmp_path, monkeypatch, capsys):
    _session(built, tmp_path, CODER, monkeypatch)
    env = (built / ".env").read_text().replace("{prompt}", "{prompt} " + str(built))
    (built / ".env").write_text(env)
    args = ["--session", "coder", "--component", "web-app", "--root", str(built)]
    assert start_session_tool.main(args) == 0
    assert "code written" in (built / ".qf/sessions/coder-web-app.log").read_text()


def test_without_a_command_nothing_starts(built, capsys):
    args = ["--session", "tester", "--component", "auth-service", "--root", str(built)]
    assert start_session_tool.main(args) == 2
    assert "QF_COMMAND_TO_START_AUTHOR_SESSIONS" in capsys.readouterr().err
    assert not (Path(built) / ".qf/sessions").exists()


RETRY = """
import pathlib, sys
assert 'retry' in sys.argv[1] and '.qf/sessions/findings.md' in sys.argv[1]
assert '20 expected cases have no test' in pathlib.Path('.qf/sessions/findings.md').read_text()
print('tests written')
"""


def test_a_retry_hands_the_tester_the_reviewers_findings(built, tmp_path, monkeypatch, capsys):
    """FB-78: the findings sit under .qf/reviews/, which the tester's copy of
    the head never holds."""
    _session(built, tmp_path, RETRY, monkeypatch)
    (built / ".qf/reviews").mkdir(parents=True)
    (built / ".qf/reviews/32-de9697f-findings.md").write_text("20 expected cases have no test\n")
    args = ["--session", "tester", "--component", "auth-service", "--root", str(built)]
    findings = ["--findings", ".qf/reviews/32-de9697f-findings.md"]
    assert start_session_tool.main([*args, *findings]) == 0
    assert json.loads(capsys.readouterr().out)["brought_back"] == []  # the findings stay out


def test_a_retry_names_the_findings_to_the_coder(built, tmp_path, monkeypatch, capsys):
    script = CODER + "assert 'retry' in prompt and '.qf/reviews/f.md' in prompt\n"
    _session(built, tmp_path, script, monkeypatch)
    env = (built / ".env").read_text().replace("{prompt}", "{prompt} " + str(built))
    (built / ".env").write_text(env)
    (built / ".qf/reviews").mkdir(parents=True)
    (built / ".qf/reviews/f.md").write_text("finding\n")
    args = ["--session", "coder", "--component", "web-app", "--findings", ".qf/reviews/f.md"]
    assert start_session_tool.main([*args, "--root", str(built)]) == 0


def test_a_findings_file_that_is_not_there_starts_nothing(built, tmp_path, monkeypatch, capsys):
    _session(built, tmp_path, RETRY, monkeypatch)
    args = ["--session", "tester", "--component", "auth-service", "--findings", "nowhere.md"]
    assert start_session_tool.main([*args, "--root", str(built)]) == 2
    assert "No findings file" in capsys.readouterr().err
