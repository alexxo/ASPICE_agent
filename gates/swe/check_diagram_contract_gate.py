"""check_diagram_contract_gate — SWE.2 (drawn first) / SWE.1 BP3: diagrams read and connected.

Every diagram is read through its adapter, whose problems are passed on as they
are (an element without an ID or label, an endpoint missing, an ID used twice, an
unreadable file or invariants file). On what was read: every edge and message
connects nodes that exist, every node takes part in a flow, and every invariant
names only elements that exist. The diagrams hold both levels: at least one
system-level diagram (architecture, workflow, dataflow, lifecycle), the picture
at a glance, and at least one sequence diagram, the software level in detail.
Every diagram keeps its picture, the page the diagram plugin renders from it
(<id>.<type>.html next to <id>.<type>.json), committed with the diagram's last
change or after it: git's order of commits is the check, so CI needs no plugin
(§ 5 stages 1 and 2, rule 21). Outside a git repository only its presence is
checked.

    python gates/swe/check_diagram_contract_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.read_archify_diagram_adapter import (  # noqa: E402
    diagram_type,
    read_archify_diagrams,
)
from tools.check_approval_order_tool import in_git  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "check_diagram_contract_gate"


def check(config: ProductConfig) -> list[Finding]:
    results = read_archify_diagrams(config.diagrams_dir, config.root)
    if not results:
        return [
            Finding(
                "NO_DIAGRAMS",
                config.relative(config.diagrams_dir),
                None,
                "No diagram found; the diagrams drawn from the wishes belong here.",
            )
        ]
    findings = _levels(config, results) + _pictures(config, [path for path, _ in results])
    for path, result in results:
        findings.extend(result.problems)
        if result.diagram is None:
            continue
        if not result.problems:  # an incomplete diagram would make its neighbours look orphaned
            findings.extend(_connected(result.diagram))
        findings.extend(_invariants(config, path, result.diagram))
    return findings


def _levels(config: ProductConfig, results) -> list[Finding]:
    types = {diagram_type(path, result) for path, result in results}
    findings = []
    if "sequence" not in types:
        findings.append(
            Finding(
                "NO_SEQUENCE_DIAGRAM",
                config.relative(config.diagrams_dir),
                None,
                "No sequence diagram found; every feature's steps are drawn in one, and the "
                "software-level requirements are derived from it.",
            )
        )
    if not types - {"sequence", None}:
        findings.append(
            Finding(
                "NO_SYSTEM_DIAGRAM",
                config.relative(config.diagrams_dir),
                None,
                "No system-level diagram found (architecture, workflow, dataflow or "
                "lifecycle); it shows the system at a glance, and the system-level "
                "requirements are derived from it.",
            )
        )
    return findings


def _pictures(config: ProductConfig, specs: list[Path]) -> list[Finding]:
    git = in_git(config.root)
    findings = []
    for spec in specs:
        picture = spec.with_suffix(".html")
        shown = config.relative(spec)
        if not picture.is_file():
            why = "has no picture"
        elif git and _ignored(config.root, picture):
            why = f"has its picture {picture.name} ignored by git, so it is not committed"
        else:
            if git and _older(config.root, picture, spec):
                findings.append(
                    Finding(
                        "PICTURE_OUTDATED",
                        config.relative(picture),
                        None,
                        f"The picture is older than its diagram {spec.name}; render it again "
                        "with the diagram plugin and commit it with the diagram.",
                    )
                )
            continue
        findings.append(
            Finding(
                "MISSING_PICTURE",
                shown,
                None,
                f"The diagram {why}; render {picture.name} next to it with the diagram plugin "
                "and commit it, so every reader sees the picture the architect approved.",
            )
        )
    return findings


def _ignored(root: Path, file: Path) -> bool:
    return _git(root, "check-ignore", "-q", str(file)).returncode == 0


def _older(root: Path, picture: Path, spec: Path) -> bool:
    """Whether the picture was last committed before the diagram's last change."""
    spec_commit, picture_commit = _last_change(root, spec), _last_change(root, picture)
    if picture_commit is None:  # the picture has changes not committed yet: the newest
        return False
    if spec_commit is None:  # the diagram has, and the picture not
        return True
    is_ancestor = _git(root, "merge-base", "--is-ancestor", spec_commit, picture_commit)
    return is_ancestor.returncode != 0


def _last_change(root: Path, file: Path) -> str | None:
    """The commit that last changed the file, or None while it has changes not committed."""
    if _git(root, "status", "--porcelain", "--", str(file)).stdout.strip():
        return None
    return _git(root, "log", "-1", "--format=%H", "--", str(file)).stdout.strip() or None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )


def _connected(diagram: dict) -> list[Finding]:
    nodes = {e["id"] for e in diagram["elements"] if e["kind"] == "node"}
    flows = [e for e in diagram["elements"] if e["kind"] in ("edge", "message")]
    findings = []
    for flow in flows:
        for end in ("from", "to"):
            if flow[end] not in nodes:
                findings.append(
                    Finding(
                        "DANGLING_ENDPOINT",
                        diagram["source"],
                        flow.get("line"),
                        f"{flow['kind'].capitalize()} {flow['id']} goes {end} '{flow[end]}', "
                        "which is not a node of the diagram; connect it to an existing node or "
                        "add the node.",
                    )
                )
    used = {flow[end] for flow in flows for end in ("from", "to")}
    for element in diagram["elements"]:
        if element["kind"] == "node" and element["id"] not in used:
            findings.append(
                Finding(
                    "ORPHAN_NODE",
                    diagram["source"],
                    element.get("line"),
                    f"Node {element['id']} ('{element['label']}') takes part in no edge or "
                    "message; connect it, or remove it if it does not belong to the flow.",
                )
            )
    return findings


def _invariants(config: ProductConfig, path: Path, diagram: dict) -> list[Finding]:
    """Invariants naming elements that do not exist (the file itself the adapter checked)."""
    file = path.with_name(f"{diagram['diagram']}.invariants.yaml")
    if not file.is_file():
        return []
    try:
        data = read_yaml_file(file)
    except YamlReadError:
        return []  # reported by the adapter as INVALID_INVARIANTS
    if not isinstance(data, dict) or not isinstance(data.get("invariants"), list):
        return []
    ids = {e["id"] for e in diagram["elements"]}
    findings = []
    for entry in data["invariants"]:
        for name in entry.get("constrains", []) if isinstance(entry, dict) else []:
            if name not in ids:
                findings.append(
                    Finding(
                        "UNKNOWN_CONSTRAINED_ELEMENT",
                        config.relative(file),
                        None,
                        f"{entry.get('id', 'An invariant')} constrains '{name}', which is not an "
                        f"element of diagram '{diagram['diagram']}'.",
                    )
                )
    return findings


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
