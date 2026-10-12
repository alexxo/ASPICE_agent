"""gates/swe/check_diagram_contract_gate.py — every diagram read faithfully and connected."""

import copy

from product_builder import ARCHITECTURE, INVARIANTS, SEQUENCE, build_product

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
