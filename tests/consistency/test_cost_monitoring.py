"""Layer 2 — the cost monitoring companion matches its guide, and nothing needs it.

monitoring/ is optional (Appendix A.1, *Cost monitoring ships with the
framework, optional*): its dashboard is generated, reads only the metrics and
labels its guide names, is loaded from where the guide mounts it, and no gate,
tool or rule of the framework refers to it.
"""

import importlib.util
import json
import re

import pytest

pytestmark = pytest.mark.layer2

FOLDER = "monitoring"


@pytest.fixture(scope="module")
def maker(repo_root):
    spec = importlib.util.spec_from_file_location(
        "make_dashboard", repo_root / FOLDER / "make_dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guide(repo_root):
    return (repo_root / FOLDER / "COST_MONITORING.md").read_text(encoding="utf-8")


def _queries(repo_root):
    board = json.loads((repo_root / FOLDER / "claude-costs.json").read_text(encoding="utf-8"))
    return [t["expr"] for p in board["panels"] for t in p.get("targets", []) if "expr" in t]


def test_the_dashboard_is_the_generators_output(repo_root, maker):
    kept = (repo_root / FOLDER / "claude-costs.json").read_text(encoding="utf-8")
    assert kept == maker.render(), "run python monitoring/make_dashboard.py"


def test_the_dashboard_reads_only_what_the_guide_names(repo_root, maker, guide):
    queries = " ".join(_queries(repo_root))
    used = set(re.findall(r"\bclaude_code_\w+", queries))
    assert used == set(maker.METRICS)
    assert all(f"`{metric}`" in guide for metric in used)
    assert all(f"`{metric}`" in guide for metric in maker.PLAN)  # the status line's
    labels = set(re.findall(r"\bqf_\w+", queries)) - set(maker.PLAN)
    assert labels <= set(maker.LABELS)
    assert all(f"`{label}`" in guide for label in labels)


def test_grafana_loads_it_where_the_guide_mounts_it(repo_root, guide):
    provider = (repo_root / FOLDER / "provider.yaml").read_text(encoding="utf-8")
    folder = re.search(r"path: (\S+)", provider).group(1)
    for unix, windows in (
        (f".framework/monitoring:{folder}:ro", f".framework\\monitoring:{folder}:ro"),
        ("monitoring/provider.yaml:/otel-lgtm/", "monitoring\\provider.yaml:/otel-lgtm/"),
    ):
        assert unix in guide and windows in guide, unix
    assert "/d/claude-costs" in guide


def test_the_stack_is_the_version_the_guide_was_tested_with(guide):
    images = re.findall(r"grafana/otel-lgtm:([^\s`]+)", guide)
    tested = [i for i in images if re.fullmatch(r"\d+\.\d+\.\d+", i)]
    assert len(tested) == 2 and len(set(tested)) == 1  # the same tag on every platform
    assert "latest" not in images


def test_nothing_in_the_framework_needs_it(repo_root):
    users = [
        path.relative_to(repo_root).as_posix()
        for top in ("agent", "tools", "gates", "skills", "plugins", "contracts", "templates")
        for path in (repo_root / top).rglob("*")
        if path.is_file()
        and path.suffix in (".py", ".md", ".yml", ".yaml", ".json")
        and "monitoring/" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert users == []


def test_the_ledger_is_read_where_the_guide_mounts_it(repo_root, maker, guide):
    """The cost of a stage: the SQLite data source the guide provisions, with
    the plugin version it was tested with, reading the ledger's table."""
    source = (repo_root / FOLDER / "costs_datasource.yaml").read_text(encoding="utf-8")
    path = re.search(r"path: (\S+)", source).group(1)
    assert path == "/data/costs/costs.sqlite"
    for unix, windows in (
        ("costs:/data/costs", "costs:/data/costs"),
        (
            "monitoring/costs_datasource.yaml:/otel-lgtm/",
            "monitoring\\costs_datasource.yaml:/otel-lgtm/",
        ),
    ):
        assert unix in guide and windows in guide, unix
    assert len(set(re.findall(r"frser-sqlite-datasource@(\d+\.\d+\.\d+)", guide))) == 1
    board = json.loads((repo_root / FOLDER / "claude-costs.json").read_text(encoding="utf-8"))
    ledger = [t for p in board["panels"] for t in p.get("targets", []) if "rawQueryText" in t]
    assert ledger and all("FROM sessions" in t["rawQueryText"] for t in ledger)


def test_every_name_has_its_own_colour(maker):
    """Every stage and kind of session the ledger can hold has a colour, and no
    two names on the dashboard share one: a colour means one thing."""
    from tools.start_session_tool import STAGES

    assert set(maker.STAGE_COLOURS) == set(STAGES.values())
    assert set(maker.KIND_COLOURS) == {*STAGES, "orchestrator"}
    maps = ("MODEL", "TOKEN", "LLM", "KIND", "STAGE")
    colours = [c.upper() for m in maps for c in getattr(maker, f"{m}_COLOURS").values()]
    colours.append(maker.SESSION_COLOURS["framework · orchestrator"].upper())
    assert len(colours) == len(set(colours))
    for kind, colour in maker.KIND_COLOURS.items():  # a session keeps its kind's colour
        assert maker.SESSION_COLOURS[f"product · {kind}"] == colour
