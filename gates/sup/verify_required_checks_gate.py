"""verify_required_checks_gate — SUP.1 BP1, BP6: the gates run on every change.

The product's CI file (qf.yaml paths.ci_file) has a job that runs the gates of
every stage reached (resolve_stage_tool.py --check), so every pull request and
every push to the main branch gets its gates check (MISSING_GATES_JOB). No host
setting is read (decision 6 of the quality assurance stage): that a change
merged with that check passing, and with the reviews it needed, is
verify_delivery_reviewed_gate's, on every push to the main branch.

    python gates/sup/verify_required_checks_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.read_yaml_blocks_tool import YamlReadError, read_yaml_file  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402

GATE = "verify_required_checks_gate"
GATES_COMMAND = "resolve_stage_tool.py"
GATES_JOB = "gates"  # the job name of templates/github/quality_gates.yml


def check(config: ProductConfig) -> list[Finding]:
    if gates_job(config.ci_file) is not None:
        return []
    return [
        Finding(
            "MISSING_GATES_JOB",
            config.relative(config.ci_file),
            None,
            f"The CI file has no job that runs {GATES_COMMAND} --check, so the gates never "
            "run; start from templates/github/quality_gates.yml.",
        )
    ]


def gates_job(ci_file: Path) -> str | None:
    """The name of the CI job that runs the gates — the check a merged pull request's
    head must have passed."""
    try:
        workflow = read_yaml_file(ci_file) if ci_file.is_file() else None
    except YamlReadError:
        return None
    jobs = (workflow or {}).get("jobs") or {}
    for key, job in jobs.items() if isinstance(jobs, dict) else ():
        for step in (job or {}).get("steps") or ():
            run = str((step or {}).get("run", ""))
            if GATES_COMMAND in run and "--check" in run:
                return str(job.get("name", key))
    return None


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
