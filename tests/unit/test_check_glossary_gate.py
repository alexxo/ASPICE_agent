"""gates/swe/check_glossary_gate.py — terms defined once, marked, used, no alias."""

from product_builder import GLOSSARY, baseline_requirements, build_product

from gates.swe.check_glossary_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _findings(root):
    return check(read_product_config(root))


def _rules(root):
    return sorted(f.rule for f in _findings(root))


def _statement(tmp_path, uid, statement, glossary=None):
    reqs = baseline_requirements()
    next(r for r in reqs["login"] if r["uid"] == uid)["statement"] = statement
    return build_product(tmp_path, requirements=reqs, glossary=glossary)


def test_gate_name_follows_the_convention():
    assert GATE == "check_glossary_gate"


def test_the_baseline_passes(product):
    assert _findings(product) == []


def test_a_missing_glossary_fails_closed(product):
    (product / "docs/glossary.md").unlink()
    assert _rules(product) == ["MISSING_GLOSSARY"]


def test_an_undefined_marked_term_is_reported(tmp_path):
    root = _statement(tmp_path, "REQ-0011", "The web app shows a _session_ banner.")
    (finding,) = _findings(root)
    assert finding.rule == "UNDEFINED_TERM"
    assert "session" in finding.message
    line = (root / finding.file).read_text().splitlines()[finding.line - 1]
    assert line.startswith("statement:")


def test_a_glossary_term_without_marks_is_reported(tmp_path):
    root = _statement(tmp_path, "REQ-0011", "The web app shows the account name.")
    assert _rules(root) == ["UNMARKED_TERM"]


def test_marks_are_matched_without_case(tmp_path):
    root = _statement(tmp_path, "REQ-0011", "The web app shows the _Account_ name.")
    assert _findings(root) == []


def test_an_alias_is_reported(tmp_path):
    glossary = [dict(GLOSSARY[0]), dict(GLOSSARY[1], aliases=["account block"])]
    root = _statement(
        tmp_path, "REQ-0011", "The web app shows an _account block_ notice.", glossary
    )
    assert _rules(root) == ["ALIAS_USED"]


def test_a_duplicate_term_is_reported(tmp_path):
    glossary = [*GLOSSARY, {"term": "Account", "definition": "Another definition."}]
    root = build_product(tmp_path, glossary=glossary)
    assert _rules(root) == ["DUPLICATE_TERM"]


def test_an_unused_term_is_reported(tmp_path):
    glossary = [*GLOSSARY, {"term": "session", "definition": "A signed-in period."}]
    root = build_product(tmp_path, glossary=glossary)
    (finding,) = _findings(root)
    assert (finding.rule, finding.file) == ("UNUSED_TERM", "docs/glossary.md")


def test_an_invalid_glossary_block_is_reported(tmp_path):
    glossary = [*GLOSSARY, {"term": "session"}]
    root = build_product(tmp_path, glossary=glossary)
    assert _rules(root) == ["SCHEMA_VIOLATION"]


def test_snake_case_words_are_not_marks(tmp_path):
    root = _statement(tmp_path, "REQ-0011", "The web app sends the user_id field.")
    assert _findings(root) == []
