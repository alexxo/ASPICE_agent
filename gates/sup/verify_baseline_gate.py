"""verify_baseline_gate — SUP.8 BP5, BP6, BP7: every release is a complete, consistent baseline.

A release is proposed as a pull request that adds a release record (release.v1)
to qf.yaml paths.releases_dir, and tagged v<version> after its merge (decisions
1 and 2 of the configuration management stage). Every record follows release.v1
and is named <version>.yaml (INCOMPLETE_RELEASE_RECORD). A record not yet
tagged — the release being proposed — has the version the Conventional Commits
since the last release tag give (WRONG_VERSION), lists exactly the
configuration items changed since that tag, and names the framework release
the submodule is pinned at (INCOMPLETE_RELEASE_RECORD). Every release tag is
annotated (TAG_NOT_ANNOTATED), on the main branch (TAG_NOT_ON_MAIN), and
contains its record (INCOMPLETE_RELEASE_RECORD) and every configuration item
(MISSING_CONFIG_ITEM). Without a release there is nothing to check.

    python gates/sup/verify_baseline_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.check_approval_order_tool import in_git  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_commit_range_tool import main_ref  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.validate_contract_tool import validate  # noqa: E402
from tools.write_release_tool import (  # noqa: E402
    changed_items,
    config_items,
    in_tree,
    last_release,
    next_version,
    pinned_framework,
    release_tags,
)

GATE = "verify_baseline_gate"
INCOMPLETE = "INCOMPLETE_RELEASE_RECORD"


def check(config: ProductConfig) -> list[Finding]:
    root = config.root
    if not in_git(root):
        return [
            Finding(
                "NOT_A_GIT_REPOSITORY",
                ".",
                None,
                "The product is not a git repository, so it has no baseline.",
            )
        ]
    tags = release_tags(root)
    findings = []
    for path in _records(config):
        findings += _record(config, path, tags)
    for tag in tags:
        findings += _tag(config, tag)
    return findings


def _records(config: ProductConfig) -> list[Path]:
    folder = config.releases_dir
    return sorted(folder.glob("*.yaml")) if folder.is_dir() else []


def _record(config: ProductConfig, path: Path, tags: list[str]) -> list[Finding]:
    file = config.relative(path)
    try:
        record = read_yaml_file(path)
    except YamlReadError as err:
        return [Finding(INCOMPLETE, file, err.line, f"Not valid YAML: {err.message}.")]
    violations = validate(record, "release")
    if violations:
        first = violations[0]
        return [
            Finding(
                INCOMPLETE,
                file,
                None,
                f"Breaks release.v1 at '{first.path or 'the record'}': {first.message}.",
            )
        ]
    version = record["version"]
    if path.stem != version:
        return [Finding(INCOMPLETE, file, None, f"The record of {version} is named {path.name}.")]
    if f"v{version}" in tags:
        return []
    findings = []
    expected = next_version(config.root)
    if version != expected:
        since = last_release(config.root) or "the start"
        findings.append(
            Finding(
                "WRONG_VERSION",
                file,
                None,
                f"The commits since {since} give version {expected}, not {version}; "
                "rewrite the record with tools/write_release_tool.py.",
            )
        )
    changed = set(changed_items(config))
    listed = set(record["changed"])
    if listed != changed:
        missing = sorted(changed - listed)
        extra = sorted(listed - changed)
        parts = [f"missing {', '.join(missing)}"] if missing else []
        parts += [f"unchanged {', '.join(extra)}"] if extra else []
        findings.append(
            Finding(
                INCOMPLETE,
                file,
                None,
                f"The changed configuration items are wrong: {'; '.join(parts)}.",
            )
        )
    framework = pinned_framework(config)
    if record["framework"] != framework:
        findings.append(
            Finding(
                INCOMPLETE,
                file,
                None,
                f"The record names framework {record['framework']}, but the submodule is "
                f"pinned at {framework or 'no framework release'}.",
            )
        )
    return findings


def _tag(config: ProductConfig, tag: str) -> list[Finding]:
    root = config.root
    findings = []
    if _git(root, "cat-file", "-t", f"refs/tags/{tag}").stdout.strip() != "tag":
        findings.append(
            Finding(
                "TAG_NOT_ANNOTATED",
                ".",
                None,
                f"Release tag {tag} is lightweight; recreate it with git tag -a, so it records "
                "who released and when.",
            )
        )
    main = main_ref(root) or "HEAD"
    if _git(root, "merge-base", "--is-ancestor", f"{tag}^{{commit}}", main).returncode != 0:
        findings.append(
            Finding(
                "TAG_NOT_ON_MAIN",
                ".",
                None,
                f"Release tag {tag} points to a commit that is not on {main}; a release is a "
                "state of the main branch.",
            )
        )
    record = f"{config.relative(config.releases_dir).rstrip('/')}/{tag[1:]}.yaml"
    if not in_tree(root, tag, record):
        findings.append(
            Finding(INCOMPLETE, record, None, f"Release tag {tag} does not contain its record.")
        )
    for item in config_items(config):
        if not in_tree(root, tag, item):
            findings.append(
                Finding(
                    "MISSING_CONFIG_ITEM",
                    item,
                    None,
                    f"Release tag {tag} does not contain configuration item {item}.",
                )
            )
    return findings


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
