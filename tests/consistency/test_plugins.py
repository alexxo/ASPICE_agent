"""Layer 2 — every method skill under plugins/ follows the method standard.

The standard is in docs/Quality_framework_documentation.md § Method skills — the
schema, with the skeleton in plugins/README.md. The checker below is applied to
every real method skill, and checks itself on a valid and on invalid samples, so
the standard is enforced even before the first method exists.
"""

import re

import pytest
import yaml

from agent.read_stages_tool import read_stages

pytestmark = pytest.mark.layer2

NAME = re.compile(r"^[a-z]+_[a-z0-9]+(_[a-z0-9]+)*_plugin$")
GROUPS = ("swe", "sup", "val")
SECTIONS = ["Goal", "Explore", "Ask", "Depth", "Steps", "Changes", "Done"]
HEADER = ["Stage", "Fills slot", "Loaded with"]
COMPLETENESS = re.compile(r"completeness\s+wins\s+over\s+a\s+budget", re.IGNORECASE)


def check_method_skill(text: str, name: str, group: str) -> list[str]:
    """Every way the text breaks the method standard; empty when it follows it."""
    problems = []
    if not NAME.match(name):
        problems.append(f"name '{name}' is not action_what_plugin")
    if group not in GROUPS:
        problems.append(f"group '{group}' is not one of {', '.join(GROUPS)}")

    front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    meta = yaml.safe_load(front.group(1)) if front else None
    if not isinstance(meta, dict):
        problems.append("no front matter")
    else:
        if meta.get("name") != name:
            problems.append(f"front matter name is not '{name}'")
        if not meta.get("description"):
            problems.append("front matter has no description")

    if not re.search(rf"^# plugin: {re.escape(name)}\s*$", text, re.M):
        problems.append(f"title is not '# plugin: {name}'")

    header = {}
    for field in HEADER:
        found = re.search(rf"^\*\*{re.escape(field)}:\*\*\s*(.+)$", text, re.M)
        if found:
            header[field] = found.group(1).strip()
        else:
            problems.append(f"header field **{field}:** missing")

    positions = []
    for section in SECTIONS:
        found = re.search(rf"^## {re.escape(section)}\s*$", text, re.M)
        if found:
            positions.append(found.start())
        else:
            problems.append(f"section '## {section}' missing")
    if len(positions) == len(SECTIONS) and positions != sorted(positions):
        problems.append(f"sections are not in the order {', '.join(SECTIONS)}")

    done = re.search(r"^## Done\s*$(.*)", text, re.M | re.S)
    if done and not COMPLETENESS.search(done.group(1)):
        problems.append("Done does not state that completeness wins over a budget")

    if len(header) == len(HEADER):
        problems.extend(_agrees_with_manifest(header))
    return problems


def _agrees_with_manifest(header: dict[str, str]) -> list[str]:
    number = re.match(r"^(\d+) · (.+)$", header["Stage"])
    if not number:
        return [f"Stage '{header['Stage']}' is not '<number> · <process>'"]
    stage = next((s for s in read_stages() if s.number == int(number.group(1))), None)
    if stage is None:
        return [f"no stage {number.group(1)} in agent/stages.yaml"]
    problems = []
    if number.group(2) != stage.process:
        problems.append(f"Stage process is not '{stage.process}'")
    if header["Fills slot"] != stage.slot:
        problems.append(f"Fills slot is not '{stage.slot}', the slot of stage {stage.number}")
    loaded = [s.strip() for s in header["Loaded with"].split(",") if s.strip()]
    if loaded != list(stage.skills):
        problems.append(f"Loaded with is not {', '.join(stage.skills) or 'empty'}")
    return problems


# ── the real method skills ──────────────────────────────────────────────────


def _methods(repo_root):
    return sorted((repo_root / "plugins").glob("*/*/SKILL.md"))


def test_every_method_skill_follows_the_standard(repo_root):
    problems = []
    for path in _methods(repo_root):
        for problem in check_method_skill(
            path.read_text(), path.parent.name, path.parent.parent.name
        ):
            problems.append(f"{path.relative_to(repo_root)}: {problem}")
    assert not problems, "\n".join(problems)


def test_the_skeleton_names_every_section_and_field(repo_root):
    skeleton = (repo_root / "plugins" / "README.md").read_text()
    for section in SECTIONS:
        assert f"## {section}" in skeleton, section
    for field in HEADER:
        assert f"**{field}:**" in skeleton, field
    assert COMPLETENESS.search(skeleton)


# ── the checker checks itself ───────────────────────────────────────────────

VALID = """---
name: derive_requirements_plugin
description: Requirements from the approved diagrams and the wishes.
---

# plugin: derive_requirements_plugin

**Stage:** 2 · SWE.1 Software requirements
**Fills slot:** create_requirements_plugin
**Loaded with:** write_requirements_skill, define_glossary_terms_skill, specify_nfr_measurement_skill

## Goal
From the approved diagrams to the requirements.

## Explore
The diagrams.

## Ask
Business rules.

## Depth
Lite or full.

## Steps
Element by element.

## Changes
Grow, never rewrite.

## Done
The gates pass. Completeness wins over a budget.
"""


def _check(text, name="derive_requirements_plugin", group="swe"):
    return check_method_skill(text, name, group)


def test_the_valid_sample_follows_the_standard():
    assert _check(VALID) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda t: t.replace("## Depth\nLite or full.\n\n", ""), "section '## Depth' missing"),
        (
            lambda t: t.replace(
                "## Explore\nThe diagrams.\n\n## Ask\nBusiness rules.\n\n",
                "## Ask\nBusiness rules.\n\n## Explore\nThe diagrams.\n\n",
            ),
            "sections are not in the order",
        ),
        (
            lambda t: t.replace(
                "**Fills slot:** create_requirements_plugin",
                "**Fills slot:** create_architecture_plugin",
            ),
            "Fills slot is not",
        ),
        (lambda t: t.replace(", specify_nfr_measurement_skill", ""), "Loaded with is not"),
        (lambda t: t.replace("SWE.1 Software requirements", "SWE.1 Requirements"), "Stage process"),
        (lambda t: t.replace(" Completeness wins over a budget.", ""), "completeness wins"),
        (
            lambda t: t.replace("name: derive_requirements_plugin\n", "name: other_plugin\n"),
            "front matter name",
        ),
        (lambda t: t.replace("# plugin: derive_requirements_plugin", "# derive"), "title is not"),
        (lambda t: t.replace("**Loaded with:**", "**Uses:**"), "**Loaded with:** missing"),
    ],
)
def test_the_checker_catches_each_breach(change, expected):
    problems = _check(change(VALID))
    assert any(expected in p for p in problems), problems


def test_a_name_outside_the_convention_is_caught():
    assert any("not action_what_plugin" in p for p in _check(VALID, name="derive-requirements"))


def test_a_group_outside_the_process_groups_is_caught():
    assert any("group" in p for p in _check(VALID, group="methods"))
