"""monitoring/plan_usage_statusline.py — the orchestrator's cost in the cost ledger."""

import importlib.util
import io
import json
from pathlib import Path

import pytest
from product_builder import ledger_rows

SCRIPT = Path(__file__).resolve().parents[2] / "monitoring/plan_usage_statusline.py"


@pytest.fixture
def statusline(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("plan_usage_statusline", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("QF_COSTS_DIR", str(tmp_path / "costs"))
    return module


def _data(where, cost=0.42):
    return {
        "session_id": "s-1",
        "workspace": {"current_dir": str(where), "repo": {"name": "Team_repo_wp_publisher"}},
        "model": {"id": "claude-opus-5-5"},
        "cost": {"total_cost_usd": cost, "total_duration_ms": 90000},
    }


def test_the_orchestrator_keeps_one_row_its_cost_the_running_total(statusline, tmp_path):
    product = tmp_path / "product"
    (product / "src").mkdir(parents=True)
    (product / "qf.yaml").write_text("contract: qf.v1\n")
    statusline.record(_data(product / "src"))  # anywhere inside the product
    statusline.record(_data(product / "src", cost=1.25))
    (row,) = ledger_rows(tmp_path / "costs")
    assert {k: row[k] for k in ("id", "product", "kind", "stage", "llm", "cost_usd")} == {
        "id": "s-1",
        "product": "Team_repo_wp_publisher",
        "kind": "orchestrator",
        "stage": None,
        "llm": "claude",
        "cost_usd": 1.25,
    }
    assert row["seconds"] == 90.0


def test_outside_a_product_nothing_is_recorded(statusline, tmp_path):
    statusline.record(_data(tmp_path))
    assert not (tmp_path / "costs").exists()


def _product(tmp_path):
    product = tmp_path / "product"
    product.mkdir()
    (product / "qf.yaml").write_text("contract: qf.v1\n")
    return product


def test_the_ledger_folder_is_read_from_the_products_env(statusline, tmp_path, monkeypatch):
    monkeypatch.delenv("QF_COSTS_DIR")
    product = _product(tmp_path)
    (product / ".env").write_text(f"# the ledger\nQF_COSTS_DIR='{tmp_path / 'from-env'}'\n")
    assert statusline.record(_data(product)) is None
    assert [r["kind"] for r in ledger_rows(tmp_path / "from-env")] == ["orchestrator"]


def test_without_a_ledger_folder_the_line_says_so(statusline, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("QF_COSTS_DIR")
    data = _data(_product(tmp_path))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
    statusline.main()
    assert capsys.readouterr().out.strip() == "cost not recorded: QF_COSTS_DIR not set"


def test_a_ledger_that_cannot_be_written_is_named(statusline, tmp_path, monkeypatch):
    blocked = tmp_path / "a-file"
    blocked.write_text("")
    monkeypatch.setenv("QF_COSTS_DIR", str(blocked))
    assert statusline.record(_data(_product(tmp_path))) == f"cannot write {blocked}"
