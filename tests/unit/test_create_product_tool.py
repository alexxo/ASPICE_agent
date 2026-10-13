"""create_product_tool — the product is the root, the framework its pinned submodule."""

import shutil
import subprocess

import pytest
import yaml

from gates.sup.verify_required_checks_gate import codeowners, gates_job, owned
from tools import create_product_tool
from tools.validate_contract_tool import validate

GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.org"]


def git(root, *command):
    return subprocess.run(
        GIT + ["-C", str(root), *command], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture(autouse=True)
def file_submodules(monkeypatch):
    """git refuses file:// submodules unless allowed; the tests' framework is a local repository."""
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "protocol.file.allow")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "always")


@pytest.fixture
def framework_repo(tmp_path, repo_root):
    """A framework repository with the real templates, released as v1.0.0, then a later commit."""
    repo = tmp_path / "framework"
    shutil.copytree(repo_root / "templates", repo / "templates")
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "feat: first")
    git(repo, "tag", "-a", "v1.0.0", "-m", "v1.0.0")
    (repo / "README.md").write_text("later\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "fix: later")
    return repo


@pytest.fixture
def cloned(tmp_path, framework_repo, monkeypatch):
    """A plain folder holding only the framework, cloned at its release into .framework."""
    root = tmp_path / "shop"
    root.mkdir()
    git(
        tmp_path,
        "clone",
        "-q",
        "--branch",
        "v1.0.0",
        framework_repo.as_uri(),
        str(root / ".framework"),
    )
    monkeypatch.setattr(create_product_tool, "FRAMEWORK", root / ".framework")
    return root


@pytest.fixture
def product(tmp_path, framework_repo, monkeypatch):
    """A product whose person already ran git init and added the submodule at its release."""
    root = tmp_path / "shop"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "submodule", "add", "-q", framework_repo.as_uri(), ".framework")
    git(root / ".framework", "checkout", "-q", "v1.0.0")
    monkeypatch.setattr(create_product_tool, "FRAMEWORK", root / ".framework")
    return root


def args(root):
    return [
        "--root",
        str(root),
        "--mirror",
        "https://gitlab.com/acme/shop.git",
        "--reviewer-agent",
        "qf-reviewer-bot",
        "--urgent-approver",
        "lead-ana",
        "--change-approver",
        "lead-ana",
        "--change-approver",
        "lead-ben",
        "--code-owner",
        "@lead-ana",
        "--code-owner",
        "@acme/architects",
    ]


def test_a_new_product_gets_a_valid_configuration(product):
    assert create_product_tool.main(args(product)) == 0

    qf = yaml.safe_load((product / "qf.yaml").read_text())
    assert validate(qf, "qf") == []
    assert qf["review"]["agents"] == ["qf-reviewer-bot"]
    assert qf["urgent_approvers"] == ["lead-ana"]
    assert qf["change_approvers"] == ["lead-ana", "lead-ben"]
    assert qf["mirror"] == "https://gitlab.com/acme/shop.git"
    assert qf["slots"]["create_diagram_plugin"] == "archify"
    assert qf["paths"]["framework_dir"] == ".framework"


def test_the_pin_at_the_release_is_staged(product, framework_repo):
    create_product_tool.main(args(product))

    tagged = git(framework_repo, "rev-parse", "v1.0.0^{commit}")
    assert git(product, "ls-files", "--stage", ".framework").startswith("160000 " + tagged)
    assert ".gitmodules" in git(product, "diff", "--cached", "--name-only")


def test_a_cloned_framework_becomes_the_submodule_of_a_new_repository(cloned, framework_repo):
    assert create_product_tool.main(args(cloned)) == 0

    assert git(cloned, "rev-parse", "--show-toplevel") == str(cloned.resolve())
    url = git(cloned, "config", "-f", ".gitmodules", "submodule..framework.url")
    assert url == framework_repo.as_uri()
    tagged = git(framework_repo, "rev-parse", "v1.0.0^{commit}")
    assert git(cloned, "ls-files", "--stage", ".framework").startswith("160000 " + tagged)
    assert (cloned / "qf.yaml").exists()


def test_a_clone_in_an_existing_repository_is_adopted(cloned, framework_repo):
    git(cloned, "init", "-q")
    (cloned / "notes.md").write_text("mine\n")
    git(cloned, "add", "notes.md")

    assert create_product_tool.main(args(cloned)) == 0

    assert "notes.md" in git(cloned, "diff", "--cached", "--name-only")
    assert ".framework" in git(cloned, "config", "-f", ".gitmodules", "--list")


def test_a_clone_without_origin_is_refused(cloned, capsys):
    git(cloned / ".framework", "remote", "remove", "origin")

    assert create_product_tool.main(args(cloned)) == 2
    assert not (cloned / ".git").exists()
    assert not (cloned / "qf.yaml").exists()
    assert "origin" in capsys.readouterr().err


def test_the_ci_files_are_the_templates(product, repo_root):
    create_product_tool.main(args(product))

    for template, target in create_product_tool.COPIED.items():
        assert (product / target).read_text() == (repo_root / template).read_text()
    assert gates_job(product / ".github/workflows/quality_gates.yml") == "gates"


def test_code_owners_guard_the_ci_file_the_pin_and_the_architecture(product):
    create_product_tool.main(args(product))

    rules, file = codeowners(product)
    assert file == ".github/CODEOWNERS"
    for path in (".github/workflows/quality_gates.yml", ".gitmodules", "docs/architecture/"):
        assert owned(rules, path), path
    assert all(names == ["@lead-ana", "@acme/architects"] for _, names in rules)


def test_the_agent_files_stay_out_of_git(product):
    (product / ".gitignore").write_text("node_modules/\n.qf/\n")
    create_product_tool.main(args(product))

    lines = (product / ".gitignore").read_text().splitlines()
    assert lines[:2] == ["node_modules/", ".qf/"]
    assert lines.count(".qf/") == 1
    assert {".agents/", ".claude/"} <= set(lines)


def test_no_work_product_and_no_empty_folder_is_created(product):
    """Wishes, diagrams and requirements are the stages' work, not the setup's."""
    create_product_tool.main(args(product))

    assert not (product / "docs").exists()
    empty = [
        p
        for p in product.rglob("*")
        if p.is_dir() and ".git" not in p.parts and not any(p.iterdir())
    ]
    assert empty == []


def test_the_product_starts_at_the_first_stage(product, capsys):
    create_product_tool.main(args(product))

    out = capsys.readouterr().out
    assert "v1.0.0" in out and "stage 1" in out
    assert "QF_HOST_TOKEN" in out and "required check" in out
    assert "archify" in out


def test_a_framework_outside_the_product_is_refused(product, framework_repo, capsys, monkeypatch):
    """The framework exists once: as the product's submodule, never a released clone beside it."""
    git(framework_repo, "checkout", "-q", "v1.0.0")
    monkeypatch.setattr(create_product_tool, "FRAMEWORK", framework_repo)

    assert create_product_tool.main(args(product)) == 2
    assert not (product / "qf.yaml").exists()
    err = capsys.readouterr().err
    assert "not the product's submodule" in err and "git clone" in err


def test_a_framework_not_at_a_release_is_refused(cloned, capsys):
    git(cloned / ".framework", "checkout", "-q", "main")

    assert create_product_tool.main(args(cloned)) == 2
    assert not (cloned / ".git").exists()
    assert not (cloned / "qf.yaml").exists()
    assert "release tag" in capsys.readouterr().err


def test_an_existing_configuration_is_never_replaced(product, capsys):
    (product / "qf.yaml").write_text("mine\n")

    assert create_product_tool.main(args(product)) == 2
    assert (product / "qf.yaml").read_text() == "mine\n"
    assert not (product / ".github").exists()
    assert "qf.yaml" in capsys.readouterr().err


def test_no_existing_file_is_overwritten(product, capsys):
    (product / ".github").mkdir()
    (product / ".github/CODEOWNERS").write_text("* @someone\n")

    assert create_product_tool.main(args(product)) == 2
    assert (product / ".github/CODEOWNERS").read_text() == "* @someone\n"
    assert not (product / "qf.yaml").exists()
    assert ".github/CODEOWNERS" in capsys.readouterr().err


def test_an_invalid_person_value_changes_nothing(cloned, capsys):
    assert create_product_tool.main(args(cloned) + ["--reviewer-agent", "not a login"]) == 2
    assert not (cloned / ".git").exists()
    assert not (cloned / "qf.yaml").exists()
    assert "review" in capsys.readouterr().err


def test_a_code_owner_must_be_a_person_or_team(product, capsys):
    assert create_product_tool.main(args(product) + ["--code-owner", "lead-ana"]) == 2
    assert not (product / "qf.yaml").exists()
    assert "lead-ana" in capsys.readouterr().err


@pytest.mark.parametrize(
    "flag",
    ["--mirror", "--reviewer-agent", "--urgent-approver", "--change-approver", "--code-owner"],
)
def test_every_person_value_is_required(product, flag):
    argv = args(product)
    while flag in argv:
        i = argv.index(flag)
        del argv[i : i + 2]
    with pytest.raises(SystemExit) as exit_:
        create_product_tool.main(argv)
    assert exit_.value.code == 2
