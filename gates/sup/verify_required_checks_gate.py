"""verify_required_checks_gate — SUP.1 BP1, BP6: the gates run on every change.

The product's CI file (qf.yaml paths.ci_file) has a job that runs the gates
(resolve_stage_tool.py --check), so every pull request and
every push to the main branch gets its gates check (MISSING_GATES_JOB). That
job keeps every step of the framework's template that runs a framework command
— the gates, the verification report, the crossing sign, the checkpoint-4
review — unchanged, in the template's order and never allowed to fail
silently (continue-on-error), with the template's triggers and permissions
(CI_FILE_NOT_TEMPLATE): a change there could switch a gate off, and no person
reviews the CI file. The product adds its own steps, such as its toolchain. No host
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
TEMPLATE = Path(__file__).resolve().parents[2] / "templates/github/quality_gates.yml"


def check(config: ProductConfig) -> list[Finding]:
    if gates_job(config.ci_file) is not None:
        return [
            Finding(
                "CI_FILE_NOT_TEMPLATE",
                config.relative(config.ci_file),
                None,
                f"The CI file differs from the framework's template: {what}. Copy it from "
                "templates/github/quality_gates.yml; only the product's own steps may differ.",
            )
            for what in template_differences(config)
        ]
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


def template_differences(config: ProductConfig) -> list[str]:
    """How the product's gates job departs from the template's framework steps,
    triggers and permissions, in words; empty when it keeps them."""
    framework = config.relative(config.framework_dir).rstrip("/")
    template = read_yaml_file(TEMPLATE)
    product = read_yaml_file(config.ci_file) or {}
    found = []
    wanted, has = _triggers(template), _triggers(product)
    found += [f"it is not triggered on {t}" for t in wanted if t not in has]
    granted = product.get("permissions") or {}
    for scope, level in (template.get("permissions") or {}).items():
        if granted.get(scope) != level:
            found.append(f"permission {scope} is not {level}")
    steps = [
        _step(step, ".framework")
        for step in _gates_steps(template)
        if ".framework/" in str(step.get("run", ""))
    ]
    mine = [_step(step, framework) for step in _gates_steps(product)]
    at = -1
    for step in steps:
        same = [i for i, m in enumerate(mine) if m["name"] == step["name"]]
        if not same:
            found.append(f"the step '{step['name']}' is missing")
            continue
        i = same[0]
        if mine[i]["continue"]:
            found.append(f"the step '{step['name']}' may fail without failing the run")
        if any(mine[i][k] != step[k] for k in ("run", "if", "env")):
            found.append(f"the step '{step['name']}' is changed")
        if i < at:
            found.append(f"the step '{step['name']}' is out of the template's order")
        at = max(at, i)
    return found


def _triggers(workflow: dict) -> list[str]:
    # YAML reads the key on as true
    on = workflow.get("on", workflow.get(True)) or {}
    return list(on) if isinstance(on, dict) else [on] if isinstance(on, str) else list(on)


def _gates_steps(workflow: dict) -> list[dict]:
    for job in ((workflow or {}).get("jobs") or {}).values():
        steps = [s for s in (job or {}).get("steps") or () if isinstance(s, dict)]
        if any(GATES_COMMAND in str(s.get("run", "")) for s in steps):
            return steps
    return []


def _step(step: dict, framework: str) -> dict:
    """A step as compared: its run with the framework path as in the template,
    each line stripped."""
    run = str(step.get("run", "")).replace(f"{framework}/", ".framework/")
    return {
        "name": str(step.get("name", step.get("uses", ""))),
        "run": "\n".join(line.strip() for line in run.strip().splitlines()),
        "if": step.get("if"),
        "env": step.get("env") or {},
        "continue": bool(step.get("continue-on-error")),
    }


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
