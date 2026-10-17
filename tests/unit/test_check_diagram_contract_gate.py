"""gates/swe/check_diagram_contract_gate.py — every diagram read faithfully and connected."""

import copy

from product_builder import (
    ARCHITECTURE,
    INVARIANTS,
    SEQUENCE,
    build_product,
    commit_all,
    write_picture,
)

from gates.swe.check_diagram_contract_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def _rules(root):
    return sorted(f.rule for f in _findings(root))


def _with_architecture(tmp_path, change):
    architecture = copy.deepcopy(ARCHITECTURE)
    change(architecture)
    diagrams = {"auth-flow.architecture.json": architecture, "login.sequence.json": SEQUENCE}
    return build_product(tmp_path, diagrams=diagrams, git=False)


def test_gate_name_follows_the_convention():
    assert GATE == "check_diagram_contract_gate"


def test_the_baseline_passes(product):
    assert _findings(product) == []


def test_no_diagrams_fails_closed(tmp_path):
    root = build_product(tmp_path, diagrams={}, invariants={}, wish_links={}, git=False)
    assert _rules(root) == ["NO_DIAGRAMS"]


def test_the_adapters_problems_are_passed_on(tmp_path):
    root = _with_architecture(tmp_path, lambda a: a["connections"][0].pop("label"))
    assert _rules(root) == ["MISSING_LABEL"]


def test_an_edge_into_nowhere_is_reported(tmp_path):
    def change(a):
        a["connections"].append(
            {"id": "store", "from": "auth-service", "to": "database", "label": "store"}
        )

    root = _with_architecture(tmp_path, change)
    (finding,) = _findings(root)
    assert finding.rule == "DANGLING_ENDPOINT"
    assert finding.file == "docs/diagrams/auth-flow.architecture.json"
    assert "database" in finding.message


def test_a_node_without_any_flow_is_reported(tmp_path):
    def change(a):
        a["components"].append({"id": "cache", "type": "database", "label": "Cache"})

    (finding,) = _findings(_with_architecture(tmp_path, change))
    assert finding.rule == "ORPHAN_NODE"
    assert "cache" in finding.message


def test_an_invariant_naming_an_unknown_element_is_reported(tmp_path):
    invariants = copy.deepcopy(INVARIANTS)
    invariants["login"]["invariants"][0]["constrains"] = ["reset-password"]
    root = build_product(tmp_path, invariants=invariants, git=False)
    (finding,) = _findings(root)
    assert (finding.rule, finding.file) == (
        "UNKNOWN_CONSTRAINED_ELEMENT",
        "docs/diagrams/login.invariants.yaml",
    )


def test_diagrams_without_a_sequence_diagram_are_reported(tmp_path):
    diagrams = {"auth-flow.architecture.json": ARCHITECTURE}
    root = build_product(tmp_path, diagrams=diagrams, invariants={}, git=False)
    assert _rules(root) == ["NO_SEQUENCE_DIAGRAM"]


def test_diagrams_without_a_system_level_diagram_are_reported(tmp_path):
    root = build_product(tmp_path, diagrams={"login.sequence.json": SEQUENCE}, git=False)
    assert _rules(root) == ["NO_SYSTEM_DIAGRAM"]


def test_an_unreadable_diagram_still_counts_for_its_level(tmp_path):
    diagrams = {"auth-flow.architecture.json": ARCHITECTURE, "login.sequence.json": {}}
    root = build_product(tmp_path, diagrams=diagrams, invariants={}, git=False)
    assert "NO_SEQUENCE_DIAGRAM" not in _rules(root)


def test_a_diagram_without_its_picture_is_reported(tmp_path):
    root = build_product(tmp_path, pictures=False, git=False)
    findings = _findings(root)
    assert [(f.rule, f.file) for f in findings] == [
        ("MISSING_PICTURE", "docs/diagrams/auth-flow.architecture.json"),
        ("MISSING_PICTURE", "docs/diagrams/login.sequence.json"),
    ]
    assert "auth-flow.architecture.html" in findings[0].message


def test_a_picture_ignored_by_git_is_not_committed(product):
    import subprocess

    picture = "docs/diagrams/login.sequence.html"
    subprocess.run(["git", "-C", str(product), "rm", "-q", "--cached", picture], check=True)
    (product / ".gitignore").write_text(f"{picture}\n")
    (finding,) = _findings(product)
    assert finding.rule == "MISSING_PICTURE" and "ignored by git" in finding.message


def test_a_diagram_changed_after_its_picture_is_reported(product):
    spec = product / "docs/diagrams/login.sequence.json"
    spec.write_text(spec.read_text().replace('"label": "session"', '"label": "session open"'))
    (finding,) = _findings(product)
    assert (finding.rule, finding.file) == ("PICTURE_OUTDATED", "docs/diagrams/login.sequence.html")
    commit_all(product, "the diagram alone")
    assert _rules(product) == ["PICTURE_OUTDATED"]


def test_a_picture_rendered_with_or_after_the_diagram_passes(product):
    spec = product / "docs/diagrams/login.sequence.json"
    spec.write_text(spec.read_text().replace('"label": "session"', '"label": "session open"'))
    commit_all(product, "the diagram first")
    write_picture(spec).write_text("<p>The picture rendered again.</p>\n")
    assert _rules(product) == []  # the picture's change is not committed yet: the newest
    commit_all(product, "then its picture")
    assert _rules(product) == []


def test_outside_git_only_the_pictures_presence_is_checked(tmp_path):
    root = build_product(tmp_path, git=False)
    spec = root / "docs/diagrams/login.sequence.json"
    spec.write_text(spec.read_text().replace('"label": "session"', '"label": "session open"'))
    assert _rules(root) == []
