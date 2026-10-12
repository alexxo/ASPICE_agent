"""Write the release record of the next release: its version, what changed, the framework.

A release is a pull request that adds a release record (release.v1) to qf.yaml
paths.releases_dir; after its merge CI tags the merge commit v<version>
(decision 1 of the configuration management stage). The version is computed,
never chosen (decision 2): from the Conventional Commits since the last release
tag, a breaking change (an ! after the type, or a BREAKING CHANGE: footer) bumps
the major number, a feat the minor, anything else the patch; the first release
is 1.0.0. The record lists the configuration items changed since that tag
(every item for the first release) and the tag of the framework release the
submodule is pinned at, read from the host.

    python tools/write_release_tool.py [--root PRODUCT]   # writes the record
    python tools/write_release_tool.py --pending          # versions not yet tagged

verify_baseline_gate recomputes all three with the same functions.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from tools.read_commit_range_tool import gitlink, submodule_url  # noqa: E402
from tools.read_host_tool import HostError, read_host, remote_slug  # noqa: E402
from tools.read_product_config_tool import (  # noqa: E402
    CONFIG_FILE,
    ConfigError,
    ProductConfig,
    read_product_config,
)

__all__ = [
    "FIRST_VERSION",
    "changed_items",
    "config_items",
    "in_tree",
    "last_release",
    "next_version",
    "pending",
    "pinned_framework",
    "record_path",
    "release_decisions",
    "release_tags",
]

FIRST_VERSION = "1.0.0"
_TAG = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_BREAKING = re.compile(r"^\w+(\([^)]*\))?!:|^BREAKING[ -]CHANGE:", re.M)
_FEAT = re.compile(r"^feat(\([^)]*\))?!?:")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def config_items(config: ProductConfig) -> list[str]:
    """The configuration items (SUP.8 BP1): qf.yaml and every path it declares —
    the framework pin included — then the product's own. The release and
    validation records are evidence of the baselines, not items (decision 9 of
    the validation stage)."""
    paths = [
        config.requirements_dir,
        config.glossary_file,
        config.wishes_file,
        config.diagrams_dir,
        config.approvals_dir,
        config.architecture_dir,
        config.decisions_dir,
        config.stack_file,
        config.detailed_design_dir,
        config.code_dir,
        config.verification_plan_file,
        config.env_variables_file,
        config.integration_tests_dir,
        config.software_tests_dir,
        config.observability_dir,
        config.framework_dir,
        config.ci_file,
        config.framework_feedback_file,
        config.validation_scenarios_dir,
    ]
    items = [CONFIG_FILE, *(config.relative(p) for p in paths), *config.config_items]
    return list(dict.fromkeys(items))


def release_tags(root: Path, rev: str | None = None) -> list[str]:
    """The release tags (v<major>.<minor>.<patch>), oldest version first; with
    rev, only those whose commit it contains."""
    args = ["tag", "--list", "v*"] + (["--merged", rev] if rev else [])
    tags = [t for t in _git(root, *args).stdout.split() if _TAG.match(t)]
    return sorted(tags, key=_key)


def _key(tag: str) -> tuple[int, ...]:
    return tuple(int(n) for n in _TAG.match(tag).groups())


def last_release(root: Path, rev: str = "HEAD") -> str | None:
    """The highest release tag rev contains, or None before the first release."""
    tags = release_tags(root, rev)
    return tags[-1] if tags else None


def next_version(root: Path, rev: str = "HEAD") -> str:
    """The version the commits since the last release tag give."""
    last = last_release(root, rev)
    if last is None:
        return FIRST_VERSION
    span = f"{last}..{rev}"
    messages = _git(root, "log", "--no-merges", "--format=%B%x00", span).stdout.split("\0")
    major, minor, patch = _key(last)
    if any(_BREAKING.search(m.strip()) for m in messages if m.strip()):
        return f"{major + 1}.0.0"
    if any(_FEAT.match(m.strip()) for m in messages if m.strip()):
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def changed_items(config: ProductConfig, rev: str = "HEAD") -> list[str]:
    """The configuration items changed since the last release tag; for the first
    release, every item rev contains. The customer's decision on the release
    (checkpoint 5) is written after its record, so it is no change of an item."""
    last = last_release(config.root, rev)
    items = config_items(config)
    if last is None:
        return [i for i in items if in_tree(config.root, rev, i)]
    decision = f":(exclude,glob){release_decisions(config)}"
    return [
        i
        for i in items
        if _git(config.root, "diff", "--quiet", last, rev, "--", i, decision).returncode != 0
    ]


def release_decisions(config: ProductConfig) -> str:
    """The glob of the customer's decisions on releases (checkpoint 5)."""
    return f"{config.relative(config.approvals_dir).rstrip('/')}/*-checkpoint-5-release.yaml"


def in_tree(root: Path, rev: str, path: str) -> bool:
    """The revision's tree has the file, folder or submodule at path."""
    return bool(_git(root, "ls-tree", rev, "--", path.rstrip("/")).stdout.strip())


def pinned_framework(config: ProductConfig, rev: str = "HEAD") -> str | None:
    """The tag of the framework release the submodule is pinned at, from the
    framework's repository on the host; None when the pin is no release."""
    path = config.relative(config.framework_dir)
    pinned = gitlink(config.root, rev, path)
    slug = remote_slug(submodule_url(config.root, path) or "")
    if pinned is None or slug is None:
        return None
    tags = [t for t, sha in read_host().release_tags(slug).items() if sha == pinned]
    return sorted(tags)[-1] if tags else None


def record_path(config: ProductConfig, version: str) -> Path:
    return config.releases_dir / f"{version}.yaml"


def pending(config: ProductConfig) -> list[str]:
    """The versions of the release records that have no tag yet."""
    tags = set(release_tags(config.root))
    records = sorted(config.releases_dir.glob("*.yaml")) if config.releases_dir.is_dir() else []
    return [r.stem for r in records if f"v{r.stem}" not in tags]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--pending", action="store_true", help="print the versions recorded but not yet tagged"
    )
    args = parser.parse_args(argv)
    try:
        config = read_product_config(args.root)
    except ConfigError as err:
        print(err.message, file=sys.stderr)
        return 2
    if args.pending:
        for version in pending(config):
            print(version)
        return 0
    last = last_release(config.root)
    if last is not None and not _git(config.root, "log", "--format=%H", f"{last}..HEAD").stdout:
        print(f"Nothing changed since {last}; there is nothing to release.", file=sys.stderr)
        return 2
    try:
        framework = pinned_framework(config)
    except HostError as err:
        print(err, file=sys.stderr)
        return 2
    if framework is None:
        print(
            "The framework submodule is not pinned at a framework release; pin one first.",
            file=sys.stderr,
        )
        return 2
    version = next_version(config.root)
    record = {
        "contract": "release.v1",
        "version": version,
        "changed": changed_items(config),
        "framework": framework,
    }
    path = record_path(config, version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(record, sort_keys=False))
    print(config.relative(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
