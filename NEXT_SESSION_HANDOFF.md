# Next Session Handoff

Last updated: 2026-04-26, Europe/Vienna.

## Operator Instructions

- Keep short `Trace:` progress lines before meaningful work units.
- Do not expose secrets from runtime files, env files, browser state, or credential stores.
- Do not reset or discard unrelated dirty work. Several repos have generated or shard-owned changes.
- Do not publish builds directly to GitHub. Source/download authority for clients is `chummer.run` only; GitHub should receive source and design changes, not release binaries.
- The Fleet may be running worker shards. Do not interrupt worker loops unless the user explicitly asks for Fleet operations.

## Current Objective

The design and Fleet have been hardened so Chummer6 flagship readiness now requires a separate user-journey tester audit. The missing UI-side artifact is intentionally a hard gate:

`/docker/chummercomplete/chummer6-ui/.codex-studio/published/USER_JOURNEY_TESTER_AUDIT.generated.json`

That audit must be created by a separate tester shard or equivalent independent tester process that runs the promoted Linux desktop binary like a real user, does not use internal APIs, captures visible evidence, and reports blocking findings instead of fixing them.

## Local Commits Not Yet Pushed

Design repo:

- Repo: `/docker/chummercomplete/chummer-design`
- Branch: `fleet/design`
- Commit: `5fe3b29 Require desktop user journey tester audit`
- Last checked status: clean.
- Suggested push if continuing the prior publish request:
  `git push origin HEAD:main`

Fleet repo:

- Repo: `/docker/fleet`
- Branch: `main`
- Commit: `67e9ecd0 Gate readiness on user journey tester audit`
- Status: `main` is ahead of `origin/main` by 1 commit, with pre-existing generated dirty files still present.
- Suggested push if continuing the prior publish request:
  `git push origin main`

## Design Changes Made

Canonical design files updated in `/docker/chummercomplete/chummer-design/products/chummer`:

- `DESKTOP_EXECUTABLE_EXIT_GATES.md`
  - Added Gate B2, a required adversarial user-journey tester audit.
  - Tester must use the Linux desktop binary as a user and must not fix code during the audit.
  - Required workflows:
    - `master_index_search_focus_stability`
    - `file_new_character_visible_workspace`
    - `minimal_character_build_save_reload`
    - `major_navigation_sanity`
    - `validation_or_export_smoke`
  - Requires at least two screenshots per workflow.
- `FLAGSHIP_UI_RELEASE_GATE.md`
  - Added release-blocking expectation for `USER_JOURNEY_TESTER_AUDIT.generated.json`.
  - Added the adversarial user-journey tester lane.
- `GOLDEN_JOURNEY_RELEASE_GATES.yaml`
  - `build_explain_publish` now requires repo proof for `chummer6-ui.user_journey_tester_audit`.
  - Requires status `pass`, Linux binary execution, no internal APIs, tester/fixer separation, zero open blocking findings, all workflow IDs, and screenshot evidence.
- `README.md`
  - Updated desktop gate summary.
- `JOURNEY_GATES.generated.json`
  - Rematerialized from the design contract.

Design verification already passed:

```bash
python3 scripts/ai/materialize_journey_gates_contract.py
python3 scripts/ai/publish_local_mirrors.py --check
bash scripts/ai/verify.sh
```

## Fleet Changes Made

Files changed and committed in `/docker/fleet`:

- `scripts/materialize_flagship_product_readiness.py`
  - Added optional `--ui-user-journey-tester-audit`.
  - Added validation for the tester audit artifact.
  - Fails `desktop_client` readiness if the audit is missing, not passing, missing discipline evidence, missing workflows, or has fewer than two screenshots per workflow.
  - Adds detailed evidence fields for missing/nonpassing/underscreenshotted workflows and open blocking findings.
- `scripts/chummer_design_supervisor.py`
  - Passes the preferred UI repo audit path into flagship readiness refresh.
- `config/projects/fleet.yaml`
  - `verify_cmd` and `supervisor_contract` now pass the required UI tester audit path.
- `tests/test_materialize_flagship_product_readiness.py`
  - Added pass-payload helper and failing-gate tests.
- `.codex-design/product/README.md`
- `.codex-design/product/GOLDEN_JOURNEY_RELEASE_GATES.yaml`
- `.codex-design/product/DESKTOP_EXECUTABLE_EXIT_GATES.md`
  - Updated by design mirror publication.

Fleet verification already passed:

```bash
python3 -m py_compile scripts/materialize_flagship_product_readiness.py scripts/chummer_design_supervisor.py
pytest -q tests/test_materialize_flagship_product_readiness.py -k "user_journey_tester_audit or recovers_windows_gate_from_aggregate_executable_proof"
git diff --check
```

Focused test result:

- `3 passed, 96 deselected`

Probe result proving the new gate is active:

```bash
python3 scripts/materialize_flagship_product_readiness.py \
  --out /tmp/FLAGSHIP_PRODUCT_READINESS.user-journey-probe.json \
  --mirror-out "" \
  --ui-user-journey-tester-audit /docker/chummercomplete/chummer6-ui/.codex-studio/published/USER_JOURNEY_TESTER_AUDIT.generated.json
```

Observed:

- Overall readiness: `fail; ready=7, warning=0, missing=1`
- `desktop_client`: `missing`
- Missing all five required tester workflows.
- Missing discipline evidence: `linux_binary_under_test`, `used_internal_apis_false`, `fix_shard_separate_true`.

This is expected until the UI repo produces a valid `USER_JOURNEY_TESTER_AUDIT.generated.json`.

## Mirror Publication State

`/docker/chummercomplete/chummer-design/scripts/ai/publish_local_mirrors.py` was run and mirror checks passed afterward.

Mirror files updated in sibling repos:

- `chummer6-core`: `.codex-design/product/README.md`, `.codex-design/product/GOLDEN_JOURNEY_RELEASE_GATES.yaml`
- `chummer6-ui`: same two files
- `chummer6-hub`: same two files
- `chummer6-mobile`: same two files
- `chummer6-ui-kit`: same two files if repo is present locally
- `chummer6-hub-registry`: same two files if repo is present locally
- `chummer6-media-factory`: same two files if repo is present locally
- `executive-assistant`: same two files if repo is present locally
- `fleet`: mirror files were included in Fleet commit `67e9ecd0`

Some sibling repos have unrelated dirty generated/source work. If committing mirror sync, stage only the `.codex-design/product` files unless the user asks for broader integration.

## Known Dirty Worktree State

`/docker/fleet` still has pre-existing generated dirty files under `.codex-studio/published/**`, including frontier, readiness, journey, support, weekly-governor, manifest, and shard-generated artifacts. They were not part of the Fleet commit and should not be reverted casually.

`/docker/chummercomplete/chummer6-ui` has many dirty files and untracked screenshot/run artifacts from UI parity and desktop exit-gate work, including:

- `.codex-design/product/GOLDEN_JOURNEY_RELEASE_GATES.yaml`
- `.codex-design/product/README.md`
- many `.codex-studio/published/**` parity and screenshot artifacts
- `Chummer.Avalonia/App.axaml.cs`
- several `Chummer.Tests/**` files
- untracked Linux desktop exit-gate run directories and workflow screenshots

Treat these as active work from the current or parallel UI effort. Do not clean them without explicit instruction.

## UI Bugs Still Needing Work

The user reported two concrete user-facing failures:

- Master Index search text field loses focus on every keyboard letter.
- `File > New Character` writes/logs that something initialized, but no visible workspace appears.

These should be fixed in `/docker/chummercomplete/chummer6-ui`, then verified through visible desktop workflow evidence. The new tester audit should catch both:

- `master_index_search_focus_stability`
- `file_new_character_visible_workspace`

## Next Concrete Steps

1. If the user wants persistence first, push the local commits:
   - `/docker/chummercomplete/chummer-design`: `git push origin HEAD:main`
   - `/docker/fleet`: `git push origin main`
2. Commit/push mirror-only `.codex-design/product` updates in sibling repos as needed, while avoiding unrelated dirty files.
3. In `chummer6-ui`, fix the Master Index focus loss and invisible New Character workspace.
4. Build/run the Linux desktop binary and create `USER_JOURNEY_TESTER_AUDIT.generated.json` with:
   - `status: pass`
   - `evidence.linux_binary_under_test: true`
   - `evidence.used_internal_apis: false`
   - `evidence.fix_shard_separate: true`
   - `evidence.open_blocking_findings_count: 0`
   - all five required workflow IDs
   - at least two screenshot paths per workflow
5. Re-run Fleet readiness with the audit path and verify `desktop_client` no longer fails because of the tester audit.
6. Only after green evidence, continue broader flagship parity and Karma Forge/LTD feedback-loop work.

## Useful Commands

Check current repo state:

```bash
git -C /docker/chummercomplete/chummer-design status --short --branch
git -C /docker/fleet status --short --branch
git -C /docker/chummercomplete/chummer6-ui status --short --branch
```

Re-run Fleet focused tests:

```bash
cd /docker/fleet
python3 -m py_compile scripts/materialize_flagship_product_readiness.py scripts/chummer_design_supervisor.py
pytest -q tests/test_materialize_flagship_product_readiness.py -k "user_journey_tester_audit or recovers_windows_gate_from_aggregate_executable_proof"
```

Probe the tester audit gate without changing published artifacts:

```bash
cd /docker/fleet
python3 scripts/materialize_flagship_product_readiness.py \
  --out /tmp/FLAGSHIP_PRODUCT_READINESS.user-journey-probe.json \
  --mirror-out "" \
  --ui-user-journey-tester-audit /docker/chummercomplete/chummer6-ui/.codex-studio/published/USER_JOURNEY_TESTER_AUDIT.generated.json
```

Design verification:

```bash
cd /docker/chummercomplete/chummer-design
python3 scripts/ai/materialize_journey_gates_contract.py
python3 scripts/ai/publish_local_mirrors.py --check
bash scripts/ai/verify.sh
```
