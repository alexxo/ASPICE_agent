"""verify_release_evidence_gate — VAL.1 BP3, BP4, BP5: what is released was validated, and accepted.

Every release tag holds its validation record (MISSING_VALIDATION_RECORD). While
a release is proposed — a release record with no tag yet — it has a validation
record that follows validation.v1 and is named after its version
(MISSING_VALIDATION_RECORD); the deployed commit is in the pull request's
history and holds the release record, and since it nothing changed but the
validation record and the customer's decision (WRONG_DEPLOYED_COMMIT, decision 8
of the validation stage); every result names an existing scenario
(UNKNOWN_SCENARIO), every automated scenario has a result (MISSING_RESULT), and
none failed (FAILED_SCENARIO, decision 11). The customer accepted the release —
checkpoint 5, given in the customer role as approval.v1 requires, still matching
both records — or the merge
waits: MISSING_CUSTOMER_DECISION, or RELEASE_REJECTED with the customer's reason
(decision 10). Without a release there is nothing to check.

    python gates/val/verify_release_evidence_gate.py [--root PRODUCT]
"""

from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the framework's packages importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.emit_findings_tool import Finding  # noqa: E402
from tools.read_approvals_tool import approval_state  # noqa: E402
from tools.read_product_config_tool import ProductConfig  # noqa: E402
from tools.run_gate_command_tool import run_gate_command  # noqa: E402
from tools.run_stack_commands_tool import read_stack  # noqa: E402
from tools.write_release_tool import (  # noqa: E402
    in_tree,
    pending,
    release_decisions,
    release_tags,
)
from tools.write_validation_record_tool import (  # noqa: E402
    read_record,
    scan_scenarios,
    validation_record_path,
)

GATE = "verify_release_evidence_gate"
MISSING = "MISSING_VALIDATION_RECORD"
WRITE = "python .framework/tools/write_validation_record_tool.py"


def check(config: ProductConfig) -> list[Finding]:
    findings = []
    for tag in release_tags(config.root):
        record = config.relative(validation_record_path(config, tag[1:]))
        if not in_tree(config.root, tag, record):
            findings.append(
                Finding(MISSING, record, None, f"Release tag {tag} does not hold its record.")
            )
    versions = pending(config)
    for version in versions:
        findings += _proposed(config, version)
    if versions:
        findings += _decision(config)
    return findings


def _proposed(config: ProductConfig, version: str) -> list[Finding]:
    record, why = read_record(config, version)
    shown = config.relative(validation_record_path(config, version))
    if record is None:
        return [
            Finding(
                MISSING,
                shown,
                None,
                f"{why}; deploy the release to staging, then run {WRITE} --environment "
                "<name> --commit <deployed sha> and enter the results run by hand.",
            )
        ]
    findings = _deployed(config, version, record["environment"]["commit"], shown)
    scenarios = scan_scenarios(config, read_stack(config))
    known = {s.path for s in scenarios}
    ran = set()
    for result in record["results"]:
        ran.add(result["scenario"])
        if result["scenario"] not in known:
            findings.append(
                Finding(
                    "UNKNOWN_SCENARIO",
                    shown,
                    None,
                    f"The record has a result for {result['scenario']}, which is no scenario.",
                )
            )
        elif result["result"] == "fail":
            note = f": {result['note']}" if result.get("note") else ""
            findings.append(
                Finding(
                    "FAILED_SCENARIO",
                    result["scenario"],
                    None,
                    f"Scenario {result['scenario']} failed on {record['environment']['name']}"
                    f"{note}. Fix it, deploy again and record the new run.",
                )
            )
    for s in scenarios:
        if s.automated and s.path not in ran:
            findings.append(
                Finding(
                    "MISSING_RESULT",
                    s.path,
                    None,
                    f"Automated scenario {s.path} has no result in {shown}; every automated "
                    "scenario runs at every release.",
                )
            )
    return findings


def _deployed(config: ProductConfig, version: str, commit: str, shown: str) -> list[Finding]:
    root = config.root
    if _git(root, "merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        why = f"the deployed commit {commit[:12]} is not in this release's history"
    else:
        # The release record is no exception: a deployment before it was no release.
        allowed = [shown, release_decisions(config)]
        changed = _git(root, "diff", "--name-only", commit, "--").stdout.split()
        changed += _git(root, "ls-files", "--others", "--exclude-standard").stdout.split()
        later = sorted(p for p in changed if not any(fnmatch.fnmatch(p, a) for a in allowed))
        if not later:
            return []
        why = (
            f"since the deployed commit {commit[:12]}, {', '.join(later[:5])} changed; "
            "what was validated is not what is released"
        )
    return [
        Finding(
            "WRONG_DEPLOYED_COMMIT",
            shown,
            None,
            f"Release {version}: {why}. Deploy the release's head and record the run again.",
        )
    ]


def _decision(config: ProductConfig) -> list[Finding]:
    state = approval_state(config, 5, "release")
    if state.status == "changes_requested":
        return [
            Finding(
                "RELEASE_REJECTED",
                config.relative(state.path),
                None,
                f"The customer rejected the release ({state.reason}); close its pull request "
                "and bring the reason back as a new or changed wish.",
            )
        ]
    if state.status == "approved":
        return []
    return [
        Finding(
            "MISSING_CUSTOMER_DECISION",
            config.relative(config.approvals_dir),
            None,
            f"The release waits for the customer's decision ({state.reason}): they approve "
            "the release pull request on the code host; copy it with "
            "agent/record_checkpoint_tool.py --checkpoint 5 --pull-request N.",
        )
    ]


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


if __name__ == "__main__":
    sys.exit(run_gate_command(GATE, check, description=__doc__.splitlines()[0]))
