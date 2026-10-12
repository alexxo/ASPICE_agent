"""verify_change_trace_gate — SUP.10 BP4: a change request traced to what it changes and why.

On every pull request for every change request its commits name, and at release
for every change request: every affected wish, diagram element and requirement
exists (UNKNOWN_AFFECTED_ITEM), and a change request and the problem that caused
it name each other — its problem's change_request is the change request, and a
problem naming a change request is named back (UNLINKED_PROBLEM; decision 6 of
the change request stage). A change request without a readable record is
check_change_record_gate's to report.

    python gates/sup/verify_change_trace_gate.py [--root PRODUCT] [--base REV]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.read_archify_diagram_adapter import read_archify_diagrams  # noqa: E402
from gates.sup.check_change_record_gate import named_in_pull_request  # noqa: E402
from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_host_tool import read_host, repository  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_requirements_tool import read_requirements  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.write_release_tool import pending  # noqa: E402
from tools.write_validation_record_tool import read_wishes  # noqa: E402

GATE = "verify_change_trace_gate"


def check(config: ProductConfig, base: str | None = None) -> list[Finding]:
    named = named_in_pull_request(config, base)
    release = bool(pending(config))
    if not named and not release:
        return []
    host, repo = read_host(), repository(config.root)
    changes = {i.number: i.record("change_request")[0] for i in host.issues(repo, "change-request")}
    problems = {i.number: i.record("problem")[0] for i in host.issues(repo, "problem")}
    wanted = set(changes) if release else set(named) & set(changes)
    existing = _items(config)
    findings = []
    for number in sorted(wanted):
        record = changes[number]
        if record is None:
            continue
        where = f"#{number}"
        for kind, ids in (record.get("affected") or {}).items():
            for item in ids:
                if item not in existing[kind]:
                    findings.append(
                        Finding(
                            "UNKNOWN_AFFECTED_ITEM",
                            where,
                            None,
                            f"Change request {where} affects {item}, which is no "
                            f"{kind[:-1]} of the product.",
                        )
                    )
        cause = record.get("problem")
        if cause is not None and (problems.get(cause) or {}).get("change_request") != number:
            findings.append(
                _unlinked(where, f"names problem #{cause}, which does not name it back")
            )
    if release:
        for number, record in sorted(problems.items()):
            target = (record or {}).get("change_request")
            if target is not None and (changes.get(target) or {}).get("problem") != number:
                findings.append(
                    _unlinked(
                        f"#{number}",
                        f"is carried by change request #{target}, which " "does not name it back",
                    )  # fmt: skip
                )
    return findings


def _unlinked(where: str, what: str) -> Finding:
    return Finding("UNLINKED_PROBLEM", where, None, f"{where} {what}.")


def _items(config: ProductConfig) -> dict[str, set[str]]:
    """The identifiers a change may affect: wishes, diagram elements, requirements."""
    elements = {
        f"{path.name.split('.', 1)[0]}#{e['id']}"
        for path, result in read_archify_diagrams(config.diagrams_dir, config.root)
        if result.diagram is not None
        for e in result.diagram["elements"]
    }
    requirements = {r.text("uid") for r in read_requirements(config) if r.text("uid")}
    return {"wishes": set(read_wishes(config)), "elements": elements, "requirements": requirements}


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
