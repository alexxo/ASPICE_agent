---
name: record_baseline_skill
description: "Rules for configuration management (SUP.8): commits and branches named by convention, the main branch's history never rewritten, every configuration item under git, the two tracks kept apart, and a release proposed as a pull request with a computed version, then tagged."
---

# skill: record_baseline_skill

**Stage:** 10 · SUP.8 Configuration management — the commit and branch rules apply at every stage
**Loaded with:** the ASPICE Agent itself; stage 10 has no plugin
**Contract:** contracts/release_contract.v1.schema.json
**Gates:** check_commit_conventions_gate, verify_history_kept_gate, check_config_items_gate, check_track_rule_gate, verify_architecture_tests_gate, verify_baseline_gate
**Replaces:** check-commit-message, check-commit-range, check-branch-name (main)

## What it governs

How every change reaches the main branch, and how a release becomes the
official baseline. A delivery is a pull request (stage 9); this rulebook
governs its commits, its branch and which paths it may change together. A
release is one more pull request: it adds a release record, the gates and the
village (seal 5, stage 11) accept it, and only after its merge does CI tag the
merge commit. Nothing is stamped before it is checked (decision 1 of the
configuration management stage).

## Inputs

- **qf.yaml** — every path (each one is a configuration item, with qf.yaml
  itself), *config_items* (the product's own) and *releases_dir*.
- **The commits since the last release tag**, for the version and the list of
  changed items; *tools/write_release_tool.py* works out both.
- **The framework's pin** at *paths.framework_dir* and its release tag.

## Contract

A commit message is a Conventional Commit, *type(scope)?!?: subject*, with type
one of feat, fix, docs, style, refactor, perf, test, build, ci, chore or revert,
and names the requirement or issue it serves (*REQ-0047*, *#12*) in its header
or body. Two branch names carry meaning: *arch/&lt;slug&gt;* on the
architecture track and *checkpoint/&lt;n&gt;* for a checkpoint's work —
*checkpoint/5* for a release, *checkpoint/3* for the stack, which is
architecture too. Any other
name is free (e.g. *feature/REQ-0047-lockout*, *chore/ignore-archify*): every
commit already names its reason.

A release record (release.v1) is *&lt;releases_dir&gt;/&lt;version&gt;.yaml*:
*version* (SemVer, no leading v), *changed* (the configuration items changed
since the previous release tag, every item for the first release) and
*framework* (the tag of the framework release the submodule is pinned at). The
version is computed, never chosen (decision 2): a breaking change (*!* after the
type, or a *BREAKING CHANGE:* footer) bumps the major number, a *feat* the
minor, anything else the patch; the first release is 1.0.0. Run

    python .framework/tools/write_release_tool.py --root .

on a *checkpoint/5* branch to write the record, and commit it as
*chore(release): &lt;version&gt;* naming the release's issue.

## Rules

| # | Rule | Checked by |
|---|---|---|
| R1 | Every non-merge commit of the pull request, and of every push to the main branch, is a Conventional Commit | check_commit_conventions_gate · NOT_CONVENTIONAL |
| R2 | Every such commit names the requirement or issue it serves, so every change on the main branch has a traceable reason | check_commit_conventions_gate · MISSING_REQUIREMENT_TOKEN |
| R3 | A branch named *arch/* or *checkpoint/* has its form: *arch/&lt;slug&gt;* or *checkpoint/&lt;n&gt;*, n 1, 2, 3 or 5; any other name is free | check_commit_conventions_gate · BAD_BRANCH_NAME |
| R4 | A push to the main branch keeps the previous main branch in its history; a rewrite is caught on the push, and the lost commits come back from any clone | verify_history_kept_gate · MAIN_REWRITTEN |
| R5 | Every configuration item exists and is tracked by git — not missing, untracked or ignored | check_config_items_gate · MISSING_CONFIG_ITEM, UNTRACKED_CONFIG_ITEM |
| R6 | A pull request that changes the architecture changes no feature-track work product, and comes from an arch/ branch or, for the stack, from checkpoint/3 | check_track_rule_gate · MIXED_TRACKS, ARCHITECTURE_OFF_BRANCH |
| R7 | A pull request that changes the architecture contains no code | verify_architecture_tests_gate · CODE_IN_ARCHITECTURE_PR |
| R8 | A release record follows release.v1, is named after its version, lists exactly the items changed since the previous release, and names the pinned framework release | verify_baseline_gate · INCOMPLETE_RELEASE_RECORD |
| R9 | A release's version is the one its commits give | verify_baseline_gate · WRONG_VERSION |
| R10 | Every release tag is annotated, on the main branch, and contains its record and every configuration item | verify_baseline_gate · TAG_NOT_ANNOTATED, TAG_NOT_ON_MAIN, INCOMPLETE_RELEASE_RECORD, MISSING_CONFIG_ITEM |
| R11 | A release tag never moves: it points to the commit of the main branch where its record first appeared | verify_baseline_gate · TAG_MOVED |
| R12 | A release is merged only after the village accepts it on its pull request | Checkpoint 5 |
| R13 | Never rewrite a pushed branch, the main branch or a pull request's: no force-push, no reset of it — the agent brings a refused push up to date by merging the main branch into its own; it rebases only a branch it has never pushed, since a stage done record or a review names the pushed commits | Review |

## Not checkable

- That every developer keeps a clone with the framework submodule fetched — the
  copy if the repository or the framework repository is lost (an accepted risk,
  Appendix A.9 of the design document).
- That a commit names the right requirement — the gate checks one is named;
  the reviewer judges which.

## Example

```yaml release
contract: release.v1
version: 1.4.0
changed:
  - docs/requirements
  - src
  - st
framework: v6.0.0
```
