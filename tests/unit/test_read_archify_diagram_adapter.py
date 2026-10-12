"""adapters/read_archify_diagram_adapter.py — Archify JSON + invariants → diagram.v1."""

import json
import subprocess
import sys

import pytest

from adapters.read_archify_diagram_adapter import read_archify_diagram, read_archify_diagrams
from tools.validate_contract_tool import validate

ARCHITECTURE = {
    "schema_version": 1,
    "diagram_type": "architecture",
    "meta": {"title": "Auth", "output": "auth-flow.html"},
    "components": [
        {"id": "web-app", "type": "frontend", "label": "Web app"},
        {"id": "auth-service", "type": "backend", "label": "Auth service"},
    ],
    "connections": [
        {"id": "signin-request", "from": "web-app", "to": "auth-service", "label": "sign in"},
    ],
}

SEQUENCE = {
    "schema_version": 1,
    "diagram_type": "sequence",
    "meta": {"title": "Login", "output": "login.html"},
    "participants": [
        {"id": "user", "type": "external", "label": "User"},
        {"id": "auth", "type": "backend", "label": "Auth service"},
    ],
    "messages": [
        {"id": "submit-credentials", "from": "user", "to": "auth", "y": 160, "label": "submit"},
        {"id": "session-opened", "from": "auth", "to": "user", "y": 190, "label": "session"},
    ],
}

INVARIANTS = """\
diagram: login
invariants:
  - id: INV-1
    statement: After five consecutive failed sign-ins the account is locked.
    constrains: [submit-credentials]
"""


def _diagram(tmp_path, spec, name):
    diagrams = tmp_path / "docs" / "diagrams"
    diagrams.mkdir(parents=True, exist_ok=True)
    path = diagrams / name
    path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return path


def _elements(result):
    return {e["id"]: e for e in result.diagram["elements"]}


def test_architecture_components_and_connections(tmp_path):
    path = _diagram(tmp_path, ARCHITECTURE, "auth-flow.architecture.json")
    result = read_archify_diagram(path, tmp_path)
    assert result.problems == []
    assert result.diagram["diagram"] == "auth-flow"
    assert result.diagram["type"] == "architecture"
    assert result.diagram["source"] == "docs/diagrams/auth-flow.architecture.json"
    elements = _elements(result)
    assert elements["web-app"]["kind"] == "node"
    assert elements["signin-request"] == {
        "id": "signin-request",
        "kind": "edge",
        "label": "sign in",
        "from": "web-app",
        "to": "auth-service",
        "line": elements["signin-request"]["line"],
    }


def test_sequence_participants_and_messages(tmp_path):
    result = read_archify_diagram(_diagram(tmp_path, SEQUENCE, "login.sequence.json"), tmp_path)
    kinds = {i: e["kind"] for i, e in _elements(result).items()}
    assert kinds == {
        "user": "node",
        "auth": "node",
        "submit-credentials": "message",
        "session-opened": "message",
    }


@pytest.mark.parametrize(
    ("diagram_type", "nodes", "edges"),
    [
        ("workflow", "nodes", "edges"),
        ("dataflow", "nodes", "flows"),
        ("lifecycle", "states", "transitions"),
    ],
)
def test_other_diagram_types_map_nodes_and_edges(tmp_path, diagram_type, nodes, edges):
    spec = {
        "schema_version": 1,
        "diagram_type": diagram_type,
        "meta": {"title": "T", "output": "t.html"},
        nodes: [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        edges: [{"id": "a-to-b", "from": "a", "to": "b", "label": "next"}],
    }
    result = read_archify_diagram(_diagram(tmp_path, spec, f"flow.{diagram_type}.json"), tmp_path)
    assert result.problems == []
    assert {i: e["kind"] for i, e in _elements(result).items()} == {
        "a": "node",
        "b": "node",
        "a-to-b": "edge",
    }


def test_each_element_has_its_line_in_the_source(tmp_path):
    path = _diagram(tmp_path, ARCHITECTURE, "auth-flow.architecture.json")
    lines = path.read_text().splitlines()
    for element in read_archify_diagram(path, tmp_path).diagram["elements"]:
        assert f'"{element["id"]}"' in lines[element["line"] - 1]


def test_invariants_file_is_merged(tmp_path):
    path = _diagram(tmp_path, SEQUENCE, "login.sequence.json")
    (path.parent / "login.invariants.yaml").write_text(INVARIANTS, encoding="utf-8")
    result = read_archify_diagram(path, tmp_path)
    assert result.problems == []
    assert _elements(result)["INV-1"] == {
        "id": "INV-1",
        "kind": "invariant",
        "label": "After five consecutive failed sign-ins the account is locked.",
        "source": "docs/diagrams/login.invariants.yaml",
        "line": 3,
    }


def test_output_follows_the_diagram_contract(tmp_path):
    path = _diagram(tmp_path, SEQUENCE, "login.sequence.json")
    (path.parent / "login.invariants.yaml").write_text(INVARIANTS, encoding="utf-8")
    assert validate(read_archify_diagram(path, tmp_path).diagram, "diagram") == []


def test_connection_without_id_is_reported_not_invented(tmp_path):
    spec = json.loads(json.dumps(ARCHITECTURE))
    del spec["connections"][0]["id"]
    path = _diagram(tmp_path, spec, "auth-flow.architecture.json")
    result = read_archify_diagram(path, tmp_path)
    (problem,) = result.problems
    assert problem.rule == "MISSING_ID"
    assert problem.file == "docs/diagrams/auth-flow.architecture.json"
    # no id to point at: the line where the connection's object starts
    assert path.read_text().splitlines()[problem.line - 1].strip() == "{"
    assert "signin-request" not in _elements(result)


def test_connection_without_label_is_reported(tmp_path):
    spec = json.loads(json.dumps(ARCHITECTURE))
    del spec["connections"][0]["label"]
    result = read_archify_diagram(_diagram(tmp_path, spec, "auth-flow.architecture.json"), tmp_path)
    assert [p.rule for p in result.problems] == ["MISSING_LABEL"]


def test_duplicate_id_is_reported(tmp_path):
    spec = json.loads(json.dumps(ARCHITECTURE))
    spec["connections"][0]["id"] = "web-app"
    result = read_archify_diagram(_diagram(tmp_path, spec, "auth-flow.architecture.json"), tmp_path)
    assert [p.rule for p in result.problems] == ["DUPLICATE_ID"]


def test_invariants_for_another_diagram_are_reported(tmp_path):
    path = _diagram(tmp_path, SEQUENCE, "login.sequence.json")
    (path.parent / "login.invariants.yaml").write_text(
        INVARIANTS.replace("diagram: login", "diagram: checkout"), encoding="utf-8"
    )
    result = read_archify_diagram(path, tmp_path)
    assert [p.rule for p in result.problems] == ["INVARIANTS_FOR_OTHER_DIAGRAM"]
    assert result.problems[0].file == "docs/diagrams/login.invariants.yaml"


def test_invariants_breaking_their_contract_are_reported(tmp_path):
    path = _diagram(tmp_path, SEQUENCE, "login.sequence.json")
    (path.parent / "login.invariants.yaml").write_text(
        INVARIANTS.replace("id: INV-1", "id: lockout"), encoding="utf-8"
    )
    result = read_archify_diagram(path, tmp_path)
    assert [p.rule for p in result.problems] == ["INVALID_INVARIANTS"]


def test_unreadable_json_gives_no_diagram(tmp_path):
    path = tmp_path / "broken.architecture.json"
    path.write_text('{"diagram_type": "architecture",', encoding="utf-8")
    result = read_archify_diagram(path, tmp_path)
    assert result.diagram is None
    assert [p.rule for p in result.problems] == ["UNREADABLE_DIAGRAM"]


def test_unsupported_diagram_type_gives_no_diagram(tmp_path):
    spec = dict(ARCHITECTURE, diagram_type="mindmap")
    result = read_archify_diagram(_diagram(tmp_path, spec, "auth-flow.mindmap.json"), tmp_path)
    assert result.diagram is None
    assert [p.rule for p in result.problems] == ["UNSUPPORTED_DIAGRAM_TYPE"]


def test_file_name_that_is_not_a_slug_is_reported(tmp_path):
    result = read_archify_diagram(
        _diagram(tmp_path, ARCHITECTURE, "Auth_Flow.architecture.json"), tmp_path
    )
    assert result.diagram is None
    assert [p.rule for p in result.problems] == ["INVALID_DIAGRAM_ID"]


def test_runs_as_a_command_from_any_directory(tmp_path, repo_root):
    path = _diagram(tmp_path, SEQUENCE, "login.sequence.json")
    adapter = repo_root / "adapters" / "read_archify_diagram_adapter.py"
    run = subprocess.run(
        [sys.executable, str(adapter), str(path), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["diagram"] == "login"


def test_a_directory_is_read_in_file_name_order(tmp_path):
    _diagram(tmp_path, SEQUENCE, "login.sequence.json")
    _diagram(tmp_path, ARCHITECTURE, "auth-flow.architecture.json")
    results = read_archify_diagrams(tmp_path / "docs" / "diagrams", tmp_path)
    assert [r.diagram["diagram"] for _, r in results] == ["auth-flow", "login"]


def test_a_missing_directory_has_no_diagrams(tmp_path):
    assert read_archify_diagrams(tmp_path / "nowhere", tmp_path) == []
