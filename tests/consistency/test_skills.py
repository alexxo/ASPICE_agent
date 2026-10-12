"""Layer 2 — the framework skills under skills/ (WP2).

A framework skill is a contract and its rules, loaded next to a plugin. Asserts:
the name follows action_what_kind and matches its directory; the header names a
contract that exists and the gates that enforce it; the required sections are
present; every rule says what checks it — a declared gate with an UPPER_SNAKE
rule ID, or a human checkpoint; and every example block in the skill validates
against the skill's contract, so a skill cannot drift from its schema.
"""

import json
import re

import pytest

yaml = pytest.importorskip("yaml")
jsonschema = pytest.importorskip("jsonschema")

pytestmark = pytest.mark.layer2

SKILL_NAME = re.compile(r"^[a-z]+_[a-z0-9]+(_[a-z0-9]+)*_skill$")
GATE_NAME = re.compile(r"^(check|verify|report|scan)_[a-z0-9]+(_[a-z0-9]+)*_gate$")
RULE_ID = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$")
SECTIONS = ["What it governs", "Inputs", "Contract", "Rules", "Not checkable", "Example"]
HEADER = ["Stage", "Loaded with", "Contract", "Gates"]


def _skills(repo_root):
    return sorted((repo_root / "skills").glob("*/*/SKILL.md"))


def _header(text, field):
    m = re.search(rf"^\*\*{re.escape(field)}:\*\*\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else None


def _rules(text):
    """Rows of the Rules table as (id, checked-by)."""
    section = re.search(r"^## Rules\n(.*?)(?=^## )", text, re.M | re.S)
    rows = []
    for line in section.group(1).splitlines() if section else []:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] in ("#", "") or set(cells[0]) <= set("-"):
            continue
        # A row the parser cannot read would otherwise be skipped silently.
        assert re.fullmatch(r"R[0-9]+", cells[0]), f"rule ID '{cells[0]}' is not R<number>"
        rows.append((cells[0], cells[2]))
    return rows


def _no_timestamps():
    class Loader(yaml.SafeLoader):
        pass

    Loader.yaml_implicit_resolvers = {
        k: [(t, r) for t, r in v if t != "tag:yaml.org,2002:timestamp"]
        for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    return Loader


def test_skills_exist(repo_root):
    names = {f.parent.name for f in _skills(repo_root)}
    for required in (
        "write_requirements_skill",
        "define_glossary_terms_skill",
        "specify_nfr_measurement_skill",
    ):
        assert required in names, f"missing skill {required}"


def test_skill_names_and_titles(repo_root):
    for f in _skills(repo_root):
        name = f.parent.name
        assert SKILL_NAME.match(name), f"{name}: not action_what_skill"
        assert re.search(
            rf"^# skill: {re.escape(name)}\s*$", f.read_text(), re.M
        ), f"{name}: title mismatch"


def test_skill_header_and_sections(repo_root):
    for f in _skills(repo_root):
        text, name = f.read_text(), f.parent.name
        for field in HEADER:
            assert _header(text, field), f"{name}: missing **{field}:**"
        for sec in SECTIONS:
            assert re.search(rf"^## {re.escape(sec)}\s*$", text, re.M), f"{name}: missing ## {sec}"


def test_skill_contract_exists(repo_root):
    for f in _skills(repo_root):
        contract = _header(f.read_text(), "Contract")
        assert (repo_root / contract).is_file(), f"{f.parent.name}: contract {contract} not found"


def test_every_rule_names_what_checks_it(repo_root):
    for f in _skills(repo_root):
        text, name = f.read_text(), f.parent.name
        gates = {g.strip() for g in _header(text, "Gates").split(",")}
        for g in gates:
            assert GATE_NAME.match(g), f"{name}: '{g}' is not a gate name"
        rules = _rules(text)
        assert rules, f"{name}: no rules"
        for rid, checked in rules:
            if checked.startswith("Checkpoint"):
                continue
            gate, _, ids = checked.partition("·")
            gate = gate.strip()
            assert gate in gates, f"{name} {rid}: '{gate}' not declared in **Gates:**"
            for rule_id in ids.split(","):
                assert RULE_ID.match(
                    rule_id.strip()
                ), f"{name} {rid}: bad rule ID '{rule_id.strip()}'"


def test_skill_examples_validate_against_the_contract(repo_root):
    loader = _no_timestamps()
    for f in _skills(repo_root):
        text, name = f.read_text(), f.parent.name
        contract = repo_root / _header(text, "Contract")
        tag = contract.name[: -len("_contract.v1.schema.json")]
        validator = jsonschema.Draft202012Validator(json.loads(contract.read_text()))
        blocks = re.findall(rf"^```yaml {re.escape(tag)}\n(.*?)^```$", text, re.M | re.S)
        assert blocks, f"{name}: no ```yaml {tag} example"
        for b in blocks:
            errs = sorted(validator.iter_errors(yaml.load(b, loader)), key=str)
            assert not errs, f"{name}: example invalid: {errs[0].message}"


def test_every_skill_has_front_matter(repo_root):
    """SKILL.md is kept so any Agent Skills host can load a skill; hosts read the
    front matter, so a skill without it is invisible to them."""
    for f in _skills(repo_root):
        name = f.parent.name
        front = re.match(r"^---\n(.*?)\n---\n", f.read_text(), re.S)
        assert front, f"{name}: no front matter"
        meta = yaml.safe_load(front.group(1))
        assert isinstance(meta, dict) and meta.get("name") == name, f"{name}: front matter name"
        assert meta.get("description"), f"{name}: front matter has no description"
