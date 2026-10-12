"""gates/sup/verify_branch_protection_gate.py — no force-push, no deletion on main."""

import pytest
from product_builder import PROTECTION, add_origin, build_product, write_host

from gates.sup.verify_branch_protection_gate import check
from tools.read_host_tool import HostError
from tools.read_product_config_tool import read_product_config


@pytest.fixture
def product(tmp_path):
    root = build_product(tmp_path / "product")
    add_origin(root)
    return root


def rules(product, tmp_path, monkeypatch, protection):
    host = write_host(tmp_path / "host.json", protection=protection)
    monkeypatch.setenv("QF_HOST_FILE", str(host))
    return sorted(f.rule for f in check(read_product_config(product)))


def test_a_branch_that_keeps_its_history_passes(product, tmp_path, monkeypatch):
    assert rules(product, tmp_path, monkeypatch, PROTECTION) == []


def test_force_pushes_allowed_are_caught(product, tmp_path, monkeypatch):
    protection = {**PROTECTION, "allow_force_pushes": True}
    assert rules(product, tmp_path, monkeypatch, protection) == ["FORCE_PUSH_ALLOWED"]


def test_deletion_allowed_is_caught(product, tmp_path, monkeypatch):
    protection = {**PROTECTION, "allow_deletions": True}
    assert rules(product, tmp_path, monkeypatch, protection) == ["DELETION_ALLOWED"]


def test_an_unprotected_branch_allows_both(product, tmp_path, monkeypatch):
    assert rules(product, tmp_path, monkeypatch, None) == ["DELETION_ALLOWED", "FORCE_PUSH_ALLOWED"]


def test_a_host_that_cannot_be_read_fails_closed(product):
    with pytest.raises(HostError):
        check(read_product_config(product))
