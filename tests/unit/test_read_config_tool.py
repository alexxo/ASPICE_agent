"""agent/read_config_tool.py — pipeline preconditions: config valid, every slot's skill found."""

import copy

import yaml
from product_builder import QF, build_installed_product, build_product, install_plugins

from agent.read_config_tool import read_config


def _rules(problems):
    return sorted(p.rule for p in problems)


def _qf(**slots):
    qf = copy.deepcopy(QF)
    qf["slots"].update(slots)
    return qf


def _environment(path, **content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(content))


def test_a_skill_in_the_products_own_folder_is_found(tmp_path):
    root = build_installed_product(tmp_path)
    config, problems = read_config(root)
    assert problems == []
    assert config.skills["create_architecture_plugin"] == root / ".agents/skills/design/SKILL.md"


def test_a_skill_installed_for_the_user_is_found(tmp_path, isolated_home):
    root = build_product(tmp_path / "product")
    install_plugins(isolated_home)
    config, problems = read_config(root)
    assert problems == []
    assert (
        config.skills["create_diagram_plugin"] == isolated_home / ".agents/skills/archify/SKILL.md"
    )


def test_skill_dirs_of_the_environment_file_are_searched(tmp_path, isolated_home):
    root = build_product(tmp_path / "product")
    install_plugins(tmp_path / "company")  # company/.agents/skills/<skill>
    _environment(
        isolated_home / ".config/quality-framework/environment.yaml",
        skill_dirs=[str(tmp_path / "company" / ".agents" / "skills")],
    )
    assert read_config(root)[1] == []


def test_a_plugin_declared_with_its_own_path_is_used(tmp_path):
    root = build_installed_product(tmp_path / "product")
    special = tmp_path / "tools" / "archify" / "SKILL.md"
    special.parent.mkdir(parents=True)
    special.write_text("archify somewhere special\n")
    _environment(root / ".qf/environment.yaml", plugins={"archify": str(special)})
    config, problems = read_config(root)
    assert problems == []
    assert config.skills["create_diagram_plugin"] == special


def test_the_project_environment_file_counts_before_the_users(tmp_path, isolated_home):
    root = build_product(tmp_path / "product")
    install_plugins(tmp_path / "project-skills")
    _environment(
        root / ".qf/environment.yaml",
        skill_dirs=[str(tmp_path / "project-skills" / ".agents" / "skills")],
    )
    _environment(
        isolated_home / ".config/quality-framework/environment.yaml",
        skill_dirs=[str(tmp_path / "nowhere")],
    )
    assert read_config(root)[1] == []


def test_relative_paths_are_relative_to_the_environment_file(tmp_path):
    root = build_product(tmp_path / "product")
    install_plugins(root / ".qf" / "vendor")
    _environment(root / ".qf/environment.yaml", skill_dirs=["vendor/.agents/skills"])
    assert read_config(root)[1] == []


def test_an_invalid_environment_file_is_reported(tmp_path):
    root = build_installed_product(tmp_path)
    _environment(root / ".qf/environment.yaml", skill_dirs=[])
    _, problems = read_config(root)
    assert _rules(problems) == ["INVALID_ENVIRONMENT"]
    assert problems[0].file == ".qf/environment.yaml"


def test_a_missing_skill_says_where_it_looked_and_how_to_fix_it(tmp_path):
    root = build_product(tmp_path)
    install_plugins(root, ["archify", "design", "apply"])
    _, problems = read_config(root)
    assert _rules(problems) == ["PLUGIN_NOT_INSTALLED"] * 2  # verify fills two slots
    message = problems[0].message
    assert "~/.agents/skills" in message and "environment.yaml" in message


def test_missing_qf_yaml_stops_everything(tmp_path):
    config, problems = read_config(tmp_path)
    assert config is None
    assert _rules(problems) == ["MISSING_CONFIG"]


def test_a_framework_method_resolves_from_the_framework(tmp_path, repo_root):
    root = build_installed_product(tmp_path)
    config, _ = read_config(root)
    expected = repo_root / "plugins/swe/derive_requirements_plugin/SKILL.md"
    assert config.skills["create_requirements_plugin"] == expected


def test_an_unknown_framework_method_is_reported(tmp_path):
    qf = _qf(create_requirements_plugin="quality-framework/no_such_plugin")
    root = build_installed_product(tmp_path, qf=qf)
    assert _rules(read_config(root)[1]) == ["UNKNOWN_FRAMEWORK_PLUGIN"]
