"""gates/swe/check_testability_gate.py — principle #15 declared in the architecture."""

from product_builder import STACK, architecture_doc, build_product

from gates.swe.check_testability_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _arch(tmp_path, change):
    doc = architecture_doc()
    change(doc)
    return build_product(tmp_path, architecture=doc, stack=STACK, git=False)


def _component(doc, cid):
    return next(c for c in doc["components"] if c["id"] == cid)


def test_gate_name_follows_the_convention():
    assert GATE == "check_testability_gate"


def test_the_baseline_architecture_passes(tmp_path):
    assert _rules(build_product(tmp_path, stack=STACK, git=False)) == []


def test_no_architecture_fails_closed(tmp_path):
    root = build_product(tmp_path, stack=STACK, git=False)
    (root / "docs/architecture/auth-flow.md").unlink()
    assert _rules(root) == ["NO_ARCHITECTURE"]


def test_a_component_without_a_composition_root_is_reported(tmp_path):
    root = _arch(tmp_path, lambda d: _component(d, "web-app").pop("composition_root"))
    assert _rules(root) == ["MISSING_COMPOSITION_ROOT"]


def test_an_external_needs_no_composition_root(tmp_path):
    external = {
        "id": "user",
        "derived_from": "auth-flow#user",
        "role": "external",
        "name": "User",
        "responsibility": "Signs in through a browser.",
    }
    root = _arch(tmp_path, lambda d: d["components"].append(external))
    assert _rules(root) == []


def test_an_interface_without_implementations_is_reported(tmp_path):
    root = _arch(tmp_path, lambda d: d["interfaces"][0].pop("implementations"))
    assert _rules(root) == ["MISSING_IMPLEMENTATIONS"]


def test_a_broken_block_is_left_to_the_design_contract_gate(tmp_path):
    """check_design_contract_gate reports what the schema breaks; reporting it
    again here would give one cause two findings."""

    def change(doc):
        doc["interfaces"][0]["implementations"] = {"real": "HTTPS client"}

    assert _rules(_arch(tmp_path, change)) == []
