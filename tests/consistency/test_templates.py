"""Layer 2 — the product CI templates run framework files that exist.

Every `python .framework/<path>` and `-r .framework/<path>` a template runs
must name a file in this tree, so the templates cannot drift from the framework
they check out.
"""

import re

import pytest
import yaml

pytestmark = pytest.mark.layer2

TEMPLATE = "templates/github/quality_gates.yml"
RELEASE = "templates/github/release.yml"


def test_template_is_valid_yaml(repo_root):
    workflow = yaml.safe_load((repo_root / TEMPLATE).read_text())
    assert workflow["jobs"]["gates"]["steps"]


@pytest.mark.parametrize("template", [TEMPLATE, RELEASE])
def test_every_framework_path_exists(repo_root, template):
    text = (repo_root / template).read_text()
    paths = re.findall(r"\.framework/([\w./-]+)", text)
    assert paths, "the template runs no framework file"
    for path in paths:
        assert (
            repo_root / path
        ).is_file(), f"{template} runs .framework/{path}, which does not exist"


def test_the_framework_is_the_products_pinned_submodule(repo_root):
    """No repository variable can change the rulebook: the framework comes with
    the product's checkout, at the commit its submodule pins (SUP.1 BP1)."""
    text = (repo_root / TEMPLATE).read_text()
    steps = yaml.safe_load(text)["jobs"]["gates"]["steps"]
    checkout = steps[0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["submodules"] is True
    assert "QF_FRAMEWORK_REF" not in text
    assert sum("actions/checkout@" in s.get("uses", "") for s in steps) == 1


def test_a_review_runs_the_gates_again(repo_root):
    """A sampled pull request waits for a person (seal 4): their review must
    re-run the gates, or it would stay red after the approval."""
    workflow = yaml.safe_load((repo_root / TEMPLATE).read_text())
    triggers = workflow.get("on", workflow.get(True))
    assert "pull_request_review" in triggers


def test_a_review_run_knows_the_pull_requests_base(repo_root):
    """github.base_ref is empty on a review event, so the base comes from the
    event's pull request, which both events carry (FB-28)."""
    workflow = yaml.safe_load((repo_root / TEMPLATE).read_text())
    base = workflow["jobs"]["gates"]["env"]["QF_BASE"]
    assert "github.event.pull_request.base.ref" in base and "github.base_ref" not in base


def test_the_gates_read_the_host_with_the_runs_own_token(repo_root):
    """No secret and no administrator's token: the token every run has, reading
    the host (decision 6 of the quality assurance stage); its one write is the
    crossing sign (rule 13)."""
    workflow = yaml.safe_load((repo_root / TEMPLATE).read_text())
    steps = workflow["jobs"]["gates"]["steps"]
    (gates,) = (s for s in steps if "resolve_stage_tool.py --root . --check" in s.get("run", ""))
    assert gates["env"]["QF_HOST_TOKEN"] == "${{ github.token }}"
    writes = {k for k, v in workflow["permissions"].items() if v != "read"}
    assert writes == {"statuses"} and workflow["permissions"]["statuses"] == "write"
    assert {"pull-requests", "checks"} <= set(workflow["permissions"])


def test_a_pull_request_shows_the_crossing_sign(repo_root):
    """Wait while the gates run, then wait or ready from their result, on the head
    of the pull request only (rule 13 of the quality assurance stage)."""
    workflow = yaml.safe_load((repo_root / TEMPLATE).read_text())
    steps = workflow["jobs"]["gates"]["steps"]
    runs = [s.get("run", "") for s in steps]
    signs = [s for s in steps if "post_merge_status_tool.py" in s.get("run", "")]
    gates = next(i for i, r in enumerate(runs) if "resolve_stage_tool.py --root . --check" in r)
    running, final = signs
    assert "--running" in running["run"] and steps.index(running) < gates
    assert "--stage-file .qf/stage.json" in final["run"] and steps.index(final) > gates
    assert final["if"] == "always() && github.event.pull_request"
    for sign in signs:
        assert "github.event.pull_request.head.sha" in sign["run"]


def test_runs_on_main_are_never_cancelled(repo_root):
    """A late run of a pull request must not overwrite a newer sign, but each push
    to main checks the commits it adds: those runs are never cancelled."""
    workflow = yaml.safe_load((repo_root / TEMPLATE).read_text())
    concurrency = workflow["concurrency"]
    assert "github.event.pull_request.number || github.run_id" in concurrency["group"]
    assert concurrency["cancel-in-progress"] == "${{ github.event_name != 'push' }}"


def _release_steps(repo_root):
    workflow = yaml.safe_load((repo_root / RELEASE).read_text())
    return workflow, workflow["jobs"]["release"]["steps"]


def test_a_release_is_tagged_only_after_its_merge(repo_root):
    """Decision 1 of the configuration management stage: nothing is stamped before
    the gates and the village accepted the release pull request."""
    workflow, steps = _release_steps(repo_root)
    triggers = workflow.get("on", workflow.get(True))
    assert list(triggers) == ["push"] and triggers["push"]["branches"] == ["main"]
    assert workflow["permissions"]["contents"] == "write"
    assert steps[0]["with"]["submodules"] is True and steps[0]["with"]["fetch-depth"] == 0


def test_the_release_is_checked_before_and_after_its_tag(repo_root):
    _, steps = _release_steps(repo_root)
    runs = [s.get("run", "") for s in steps]
    (tag,) = (i for i, r in enumerate(runs) if 'git tag -a "v$versions"' in r)
    baseline = [i for i, r in enumerate(runs) if "verify_baseline_gate.py" in r]
    assert baseline[0] < tag < baseline[1]
    assert "--pending" in runs[tag] and "git push origin" in runs[tag]
