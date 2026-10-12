"""agent/load_skills_tool.py — the slot's plugin plus the stage's framework skills."""

import pytest
from product_builder import build_installed_product

from agent.load_skills_tool import load_skills


def test_requirements_stage_loads_plugin_and_framework_skills(tmp_path, repo_root):
    root = build_installed_product(tmp_path)
    loaded = load_skills(root, "requirements")
    assert loaded["plugin"] == {
        "slot": "create_requirements_plugin",
        "name": "quality-framework/derive_requirements_plugin",
        "skill_file": str(repo_root / "plugins/swe/derive_requirements_plugin/SKILL.md"),
    }
    assert loaded["framework_skills"] == [
        str(repo_root / "skills/swe/write_requirements_skill/SKILL.md"),
        str(repo_root / "skills/swe/define_glossary_terms_skill/SKILL.md"),
        str(repo_root / "skills/swe/specify_nfr_measurement_skill/SKILL.md"),
    ]


def test_requirements_stage_loads_no_second_plugin(tmp_path):
    assert load_skills(build_installed_product(tmp_path), "requirements")["also_plugins"] == []


def test_detailed_design_stage_also_loads_the_diagram_plugin(tmp_path, repo_root):
    """Stage 4's method asks the diagram plugin for the design diagrams (also_slots)."""
    root = build_installed_product(tmp_path)
    loaded = load_skills(root, "detailed_design")
    assert loaded["plugin"]["name"] == "quality-framework/derive_detailed_design_plugin"
    assert loaded["framework_skills"] == [
        str(repo_root / "skills/swe/write_detailed_design_skill/SKILL.md"),
        str(repo_root / "skills/swe/validate_env_config_skill/SKILL.md"),
    ]
    (also,) = loaded["also_plugins"]
    assert (also["slot"], also["name"]) == ("create_diagram_plugin", "archify")
    assert also["skill_file"].endswith("SKILL.md")


def test_a_stage_without_a_slot_loads_only_its_rulebooks(tmp_path, repo_root):
    """Stage 10 has no crew: the agent prepares the release with its rulebook."""
    loaded = load_skills(build_installed_product(tmp_path), "configuration_management")
    assert (loaded["plugin"], loaded["also_plugins"]) == (None, [])
    assert loaded["framework_skills"] == [
        str(repo_root / "skills/sup/record_baseline_skill/SKILL.md")
    ]


def test_a_stage_that_is_not_implemented_is_refused(tmp_path, monkeypatch):
    """Every stage is built today; a manifest may still mark one as not built."""
    from dataclasses import replace

    import agent.load_skills_tool as tool
    from agent.read_stages_tool import stage

    monkeypatch.setattr(tool, "stage", lambda sid: replace(stage(sid), implemented=False))
    root = build_installed_product(tmp_path)
    with pytest.raises(ValueError, match="not implemented"):
        load_skills(root, "change_request")


def test_preconditions_must_hold(tmp_path):
    with pytest.raises(ValueError, match="MISSING_CONFIG"):
        load_skills(tmp_path, "requirements")
