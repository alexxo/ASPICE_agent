"""tools/write_release_tool.py — the next release's version, changed items and framework."""

import subprocess

import pytest
import yaml
from product_builder import (
    QF,
    add_framework,
    build_product,
    commit_all,
    make_framework,
    tag_release,
    write_host,
)

from tools.read_product_config_tool import read_product_config
from tools.validate_contract_tool import validate
from tools.write_release_tool import (
    changed_items,
    config_items,
    main,
    next_version,
    pending,
    pinned_framework,
)


def change(root, path, message):
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(f"{message}\n")
    commit_all(root, message)


@pytest.fixture
def product(tmp_path, monkeypatch):
    framework = make_framework(tmp_path / "framework")
    root = build_product(tmp_path / "product")
    add_framework(root, tmp_path / "framework")
    host = write_host(tmp_path / "host.json", tags={"v6.0.0": framework})
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return root


def test_the_items_are_every_declared_path_with_the_pin_and_the_products_own(tmp_path):
    root = build_product(tmp_path / "product", qf={**QF, "config_items": ["docs/runbooks"]})
    items = config_items(read_product_config(root))
    assert items[0] == "qf.yaml"
    assert {".framework", "src", "docs/requirements", "docs/runbooks"} <= set(items)
    assert "releases" not in items


def test_the_first_release_is_1_0_0_and_lists_every_item_it_contains(product):
    config = read_product_config(product)
    assert next_version(product) == "1.0.0"
    changed = changed_items(config)
    assert {"qf.yaml", ".framework", "docs/requirements"} <= set(changed)
    assert "src" not in changed  # no code yet


@pytest.mark.parametrize(
    ("message", "version"),
    [
        ("fix(auth): count failures once REQ-0047", "1.0.1"),
        ("docs: explain the lockout REQ-0047", "1.0.1"),
        ("feat(auth): lock the account REQ-0047", "1.1.0"),
        ("feat(auth)!: drop the old sign-in REQ-0047", "2.0.0"),
        ("fix: rename a field REQ-0047\n\nBREAKING CHANGE: clients must send email", "2.0.0"),
    ],
)
def test_the_version_follows_the_commits_since_the_last_release(product, message, version):
    tag_release(product, "1.0.0")
    change(product, "src/auth/lockout.py", "fix(auth): first REQ-0047")
    change(product, "src/auth/lockout.py", message)
    assert next_version(product) == version


def test_only_the_highest_release_tag_counts(product):
    tag_release(product, "1.0.0")
    change(product, "src/a.py", "feat: a REQ-0047")
    tag_release(product, "1.1.0")
    change(product, "src/a.py", "fix: b REQ-0047")
    subprocess.run(["git", "-C", str(product), "tag", "not-a-release"], check=True)
    assert next_version(product) == "1.1.1"


def test_only_the_items_changed_since_the_last_release_are_listed(product):
    tag_release(product, "1.0.0")
    change(product, "src/auth/lockout.py", "feat(auth): lock REQ-0047")
    change(product, "notes.txt", "docs: not an item REQ-0047")
    assert changed_items(read_product_config(product)) == ["src"]


def test_the_framework_is_the_release_tag_of_the_pin(product, tmp_path, monkeypatch):
    config = read_product_config(product)
    assert pinned_framework(config) == "v6.0.0"
    monkeypatch.setenv("QF_HOST_FILE", str(write_host(tmp_path / "other.json", tags={})))
    assert pinned_framework(config) is None


def test_the_record_is_written_and_follows_its_contract(product, capsys):
    assert main(["--root", str(product)]) == 0
    assert capsys.readouterr().out.strip() == "releases/1.0.0.yaml"
    record = yaml.safe_load((product / "releases/1.0.0.yaml").read_text())
    assert validate(record, "release") == []
    assert (record["version"], record["framework"]) == ("1.0.0", "v6.0.0")


def test_nothing_is_released_when_nothing_changed(product, capsys):
    tag_release(product, "1.0.0")
    assert main(["--root", str(product)]) == 2
    assert "Nothing changed since v1.0.0" in capsys.readouterr().err


def test_an_unreleased_framework_pin_stops_the_record(product, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("QF_HOST_FILE", str(write_host(tmp_path / "other.json", tags={})))
    assert main(["--root", str(product)]) == 2
    assert not (product / "releases").exists()
    assert "not pinned at a framework release" in capsys.readouterr().err


def test_pending_lists_the_records_without_a_tag(product, capsys):
    main(["--root", str(product)])
    commit_all(product, "chore(release): 1.0.0 #1")
    assert pending(read_product_config(product)) == ["1.0.0"]
    tag_release(product, "1.0.0")
    capsys.readouterr()
    assert main(["--root", str(product), "--pending"]) == 0
    assert capsys.readouterr().out == ""


def test_the_release_evidence_is_no_changed_item(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    from product_builder import (
        ALL_SCENARIOS,
        build_releasable_product,
        passed,
        propose_release,
        record_validation,
    )

    from agent.record_checkpoint_tool import record_checkpoint

    root, host = build_releasable_product(tmp_path)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    tag_release(root, "1.0.0")
    (root / "src/fix.py").write_text("FIX = 1\n")
    commit_all(root, "fix: a fix #3")
    propose_release(root, "1.0.1")
    config = read_product_config(root)
    assert changed_items(config) == ["src"]
    record_validation(root, passed(*ALL_SCENARIOS), version="1.0.1")
    now = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
    record_checkpoint(root, 5, "approved", "Carla Village", "customer", now=now)
    commit_all(root, "docs(approvals): the customer accepts #2")
    assert changed_items(config) == ["src"]
    assert next_version(root) == "1.0.1"
