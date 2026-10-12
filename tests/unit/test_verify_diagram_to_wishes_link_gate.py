"""gates/swe/verify_diagram_to_wishes_link_gate.py — every behaviour wish realised by a diagram."""

import copy

from product_builder import WISH_LINKS, WISHES, build_product

from gates.swe.verify_diagram_to_wishes_link_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def _rules(root):
    return sorted(f.rule for f in _findings(root))


def _links(tmp_path, change):
    links = copy.deepcopy(WISH_LINKS)
    change(links)
    return build_product(tmp_path, wish_links=links, git=False)


def test_gate_name_follows_the_convention():
    assert GATE == "verify_diagram_to_wishes_link_gate"


def test_the_baseline_passes(product):
    assert _findings(product) == []


def test_no_wishes_fails_closed(tmp_path):
    root = build_product(tmp_path, wishes=[], git=False)
    assert "NO_WISHES" in _rules(root)


def test_a_behaviour_wish_no_element_realises_is_reported(tmp_path):
    root = _links(tmp_path, lambda links: links["login"]["links"].pop("INV-1"))
    (finding,) = _findings(root)
    assert (finding.rule, finding.file) == ("UNCOVERED_WISH", "docs/wishes.md")
    assert "W-02" in finding.message


def test_a_constraint_wish_needs_no_element(product):
    """W-03 (Java 21) is a constraint: linked nowhere, and no finding."""
    assert not any("W-03" in f.message for f in _findings(product))


def test_a_constraint_wish_that_is_a_behaviour_is_reported(tmp_path):
    wishes = copy.deepcopy(WISHES)
    next(w for w in wishes if w["id"] == "W-03").pop("kind")
    root = build_product(tmp_path, wishes=wishes, git=False)
    assert _rules(root) == ["UNCOVERED_WISH"]


def test_a_diagram_without_its_wishes_file_is_reported(tmp_path):
    root = build_product(tmp_path, wish_links={"login": WISH_LINKS["login"]}, git=False)
    assert "MISSING_WISH_LINKS" in _rules(root)


def test_a_link_to_an_unknown_element_is_reported(tmp_path):
    root = _links(tmp_path, lambda links: links["login"]["links"].update({"reset": ["W-01"]}))
    assert _rules(root) == ["UNKNOWN_ELEMENT"]


def test_a_link_to_an_unknown_wish_is_reported(tmp_path):
    root = _links(tmp_path, lambda links: links["login"]["links"].update({"web-app": ["W-09"]}))
    assert _rules(root) == ["UNKNOWN_WISH"]


def test_an_invalid_wishes_file_is_reported(tmp_path):
    root = _links(tmp_path, lambda links: links["login"].update(links={}))
    assert "INVALID_WISH_LINKS" in _rules(root)
