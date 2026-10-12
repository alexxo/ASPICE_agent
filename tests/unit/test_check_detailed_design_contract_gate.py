"""gates/swe/check_detailed_design_contract_gate.py — the detailed design of SWE.3 BP1/BP2/BP4."""

from product_builder import ENV_VARIABLES, STACK, build_product, detailed_design_doc

from gates.swe.check_detailed_design_contract_gate import GATE, check
from tools.read_product_config_tool import read_product_config


def _rules(root):
    return sorted(f.rule for f in check(read_product_config(root)))


def _design(tmp_path, change=None):
    design = detailed_design_doc()
    if change:
        change(design)
    return build_product(tmp_path, stack=STACK, detailed_design=design, git=False)


def _unit(design, component, uid):
    return next(u for u in design[component]["units"] if u["id"] == uid)


def _auth(design):
    return design["auth-service"]


def test_gate_name_follows_the_convention():
    assert GATE == "check_detailed_design_contract_gate"


def test_the_baseline_detailed_design_passes(tmp_path):
    assert _rules(_design(tmp_path)) == []


# R1 — every component has its design, every design a component


def test_no_detailed_design_fails_closed(tmp_path):
    assert _rules(build_product(tmp_path, stack=STACK, git=False)) == ["NO_DETAILED_DESIGN"]


def test_a_component_without_its_design_is_reported(tmp_path):
    assert _rules(_design(tmp_path, lambda d: d.pop("web-app"))) == ["MISSING_DETAILED_DESIGN"]


def test_a_design_of_no_component_is_reported(tmp_path):
    def change(d):
        d["billing"] = d.pop("web-app")

    assert _rules(_design(tmp_path, change)) == [
        "MISSING_DETAILED_DESIGN",
        "UNKNOWN_COMPONENT",
    ]


# R2, R3 — readable blocks, contract, unique IDs


def test_a_schema_violation_is_reported(tmp_path):
    root = _design(tmp_path, lambda d: _unit(d, "web-app", "signin-form").pop("outputs"))
    assert _rules(root) == ["SCHEMA_VIOLATION"]


def test_a_unit_id_used_in_two_components_is_reported(tmp_path):
    def change(d):
        unit = _unit(d, "web-app", "signin-form")
        unit["id"] = "open-session"

    assert "DUPLICATE_ID" in _rules(_design(tmp_path, change))


# R4 — the design diagrams


def test_a_component_without_its_structure_diagram_is_reported(tmp_path):
    def change(d):
        d["web-app"]["structure"] = None

    assert _rules(_design(tmp_path, change)) == ["MISSING_DESIGN_DIAGRAM"]


def test_calls_without_a_sequence_diagram_are_reported(tmp_path):
    def change(d):
        _auth(d)["sequence"] = None

    assert _rules(_design(tmp_path, change)) == ["MISSING_DESIGN_DIAGRAM"]


def test_a_message_to_a_missing_participant_is_reported(tmp_path):
    def change(d):
        _auth(d)["sequence"]["messages"][0]["to"] = "nobody"

    assert "DANGLING_ENDPOINT" in _rules(_design(tmp_path, change))


def test_the_diagram_plugin_problems_are_reported(tmp_path):
    def change(d):
        del _auth(d)["structure"]["components"][1]["label"]

    assert "MISSING_LABEL" in _rules(_design(tmp_path, change))


# R5 — units and the structure diagram's nodes


def test_a_unit_from_no_node_is_reported(tmp_path):
    def change(d):
        _unit(d, "web-app", "signin-form")["derived_from"] = "web-app#nowhere"

    assert "UNKNOWN_ELEMENT" in _rules(_design(tmp_path, change))


def test_a_unit_from_another_components_diagram_is_reported(tmp_path):
    def change(d):
        # signin-form is a node of web-app's diagram, but the reference names auth-service's
        _unit(d, "web-app", "signin-form")["derived_from"] = "auth-service#signin-form"

    assert "UNKNOWN_ELEMENT" in _rules(_design(tmp_path, change))


def test_a_node_without_a_unit_is_reported(tmp_path):
    def change(d):
        d["web-app"]["structure"]["components"].append(
            {"id": "spinner", "type": "frontend", "label": "spinner"}
        )

    assert _rules(_design(tmp_path, change)) == ["UNCOVERED_NODE"]


# R6, R7 — calls inside the component, ranges


def test_a_call_to_no_unit_of_the_component_is_reported(tmp_path):
    def change(d):
        _unit(d, "web-app", "signin-form")["calls"] = ["check-credentials"]

    assert "UNKNOWN_UNIT" in _rules(_design(tmp_path, change))


def test_a_range_upside_down_is_reported(tmp_path):
    def change(d):
        _unit(d, "auth-service", "count-failures")["inputs"][0]["range"] = {"min": 5, "max": 0}

    assert _rules(_design(tmp_path, change)) == ["INVALID_RANGE"]


# R8, R9 — the sequence diagram agrees with the calls


def test_a_participant_that_is_no_unit_is_reported(tmp_path):
    def change(d):
        _auth(d)["sequence"]["participants"].append({"id": "cache", "type": "db", "label": "c"})

    assert _rules(_design(tmp_path, change)) == ["UNKNOWN_PARTICIPANT"]


def test_a_call_not_shown_as_a_message_is_reported(tmp_path):
    def change(d):
        _auth(d)["sequence"]["messages"].pop()

    assert _rules(_design(tmp_path, change)) == ["UNSHOWN_CALL"]


def test_a_message_that_is_no_call_is_reported(tmp_path):
    def change(d):
        _auth(d)["sequence"]["messages"].append(
            {"id": "x", "from": "count-failures", "to": "open-session", "y": 300, "label": "x"}
        )

    assert _rules(_design(tmp_path, change)) == ["UNDECLARED_CALL"]


def test_a_reply_to_a_call_is_no_undeclared_call(tmp_path):
    def change(d):
        _auth(d)["sequence"]["messages"].append(
            {"id": "r", "from": "open-session", "to": "check-credentials", "y": 300, "label": "ok"}
        )

    assert _rules(_design(tmp_path, change)) == []


# R10 — the structure diagram's edges agree with the calls


def test_a_call_not_drawn_as_an_edge_is_reported(tmp_path):
    def change(d):
        _auth(d)["structure"]["connections"].pop()

    assert _rules(_design(tmp_path, change)) == ["UNDRAWN_CALL"]


def test_an_edge_that_is_no_call_is_reported(tmp_path):
    def change(d):
        _auth(d)["structure"]["connections"].append(
            {"id": "x", "from": "count-failures", "to": "open-session", "label": "x"}
        )

    assert _rules(_design(tmp_path, change)) == ["UNDECLARED_EDGE"]


def test_a_reversed_edge_is_no_reply_in_the_structure_diagram(tmp_path):
    """Replies belong to the sequence diagram; a structure edge is a call."""

    def change(d):
        _auth(d)["structure"]["connections"].append(
            {"id": "back", "from": "open-session", "to": "check-credentials", "label": "x"}
        )

    assert _rules(_design(tmp_path, change)) == ["UNDECLARED_EDGE"]


# Environment variables declared with the design (decision 23)


def _with_variables(tmp_path, variables):
    return build_product(
        tmp_path,
        stack=STACK,
        detailed_design=detailed_design_doc(),
        env_variables=variables,
        git=False,
    )


def test_declared_variables_pass_and_none_is_fine(tmp_path):
    assert _rules(_with_variables(tmp_path / "a", ENV_VARIABLES)) == []
    assert _rules(_with_variables(tmp_path / "b", None)) == []


def test_a_variable_breaking_its_contract_is_reported(tmp_path):
    variable = {**ENV_VARIABLES[0], "required": "yes"}
    assert _rules(_with_variables(tmp_path, [variable])) == ["SCHEMA_VIOLATION"]


def test_a_variable_declared_twice_is_reported(tmp_path):
    assert _rules(_with_variables(tmp_path, ENV_VARIABLES * 2)) == ["DUPLICATE_VARIABLE"]


def test_an_unreadable_variable_block_is_reported(tmp_path):
    root = _with_variables(tmp_path, ENV_VARIABLES)
    (root / "docs" / "configuration.md").write_text("```yaml env_variable\nname: [\n```\n")
    assert _rules(root) == ["UNREADABLE_BLOCK"]
