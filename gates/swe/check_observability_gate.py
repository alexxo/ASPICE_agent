"""check_observability_gate — principles #37–#39: every observability requirement watched.

Every requirement of kind observability is named, as @sdoc[<REQ-UID>], by at
least one alert, dashboard or health-check definition under qf.yaml
paths.observability_dir (UNOBSERVED_REQUIREMENT); no definition names a
requirement that does not exist (decision 9 of the software verification
stage). That the release deployed them joins this gate with the release step.

    python gates/swe/check_observability_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_requirements_tool import read_requirements  # noqa: E402
from tools.read_software_tool import valid_requirements  # noqa: E402
from tools.read_unit_markers_tool import markers  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "check_observability_gate"


def check(config: ProductConfig) -> list[Finding]:
    known = {r.data.get("uid") for r in read_requirements(config)}
    observed = [r for r in valid_requirements(config) if r.data["kind"] == "observability"]
    named: set[str] = set()
    findings: list[Finding] = []
    for path, text in _definitions(config.observability_dir):
        for uid, line in markers(text)[1].items():
            named.add(uid)
            if uid not in known:
                findings.append(
                    Finding(
                        "UNKNOWN_REQUIREMENT",
                        config.relative(path),
                        line,
                        f"@sdoc[{uid}] names no requirement.",
                    )
                )
    for req in observed:
        uid = req.data["uid"]
        if uid not in named:
            findings.append(
                Finding(
                    "UNOBSERVED_REQUIREMENT",
                    req.file,
                    req.line("watched_by"),
                    f"Observability requirement {uid} is named by no alert, dashboard or "
                    f"health-check definition under {config.relative(config.observability_dir)}.",
                )
            )
    return findings


def _definitions(folder: Path) -> list[tuple[Path, str]]:
    """Every text file under the folder, hidden folders left out."""
    found = []
    for path in sorted(folder.rglob("*")) if folder.is_dir() else []:
        inner = path.relative_to(folder)
        if not path.is_file() or any(p.startswith(".") for p in inner.parts):
            continue
        try:
            found.append((path, path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
    return found


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
