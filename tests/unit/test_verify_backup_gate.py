"""gates/sup/verify_backup_gate.py — every release tag in the mirror."""

import subprocess

import pytest
from product_builder import QF, build_product, commit_all, tag_release

from gates.sup.verify_backup_gate import MirrorError, check
from tools.read_product_config_tool import read_product_config


def git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True)


@pytest.fixture
def mirror(tmp_path):
    path = tmp_path / "mirror.git"
    git("init", "-q", "--bare", str(path))
    return path


@pytest.fixture
def product(tmp_path, mirror):
    return build_product(tmp_path / "product", qf={**QF, "mirror": str(mirror)})


def rules(root):
    return [f.rule for f in check(read_product_config(root))]


def test_a_product_before_its_first_release_never_reads_the_mirror(tmp_path):
    root = build_product(tmp_path / "p", qf={**QF, "mirror": str(tmp_path / "nowhere")})
    assert rules(root) == []


def test_a_mirrored_release_passes(product, mirror):
    tag_release(product, "1.0.0")
    git("-C", str(product), "push", "-q", str(mirror), "v1.0.0")
    assert rules(product) == []


def test_a_release_missing_from_the_mirror_is_caught(product, mirror):
    tag_release(product, "1.0.0")
    git("-C", str(product), "push", "-q", str(mirror), "v1.0.0")
    commit_all(product, "fix: x REQ-0047")
    tag_release(product, "1.0.1")
    found = check(read_product_config(product))
    assert [f.rule for f in found] == ["TAG_NOT_IN_MIRROR"]
    assert "v1.0.1" in found[0].message


def test_a_mirrored_tag_that_differs_is_caught(product, mirror, tmp_path):
    tag_release(product, "1.0.0")
    git("-C", str(product), "push", "-q", str(mirror), "v1.0.0")
    git("-C", str(product), "tag", "-d", "v1.0.0")
    commit_all(product, "fix: retag REQ-0047")
    tag_release(product, "1.0.0")
    assert rules(product) == ["TAG_NOT_IN_MIRROR"]


def test_an_unreachable_mirror_fails_closed(tmp_path):
    root = build_product(tmp_path / "p", qf={**QF, "mirror": str(tmp_path / "nowhere")})
    tag_release(root, "1.0.0")
    with pytest.raises(MirrorError, match="cannot be read"):
        check(read_product_config(root))
