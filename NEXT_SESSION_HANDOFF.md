# Next Session Handoff

Last updated: 2026-05-17, Europe/Vienna.

## Operator Instructions

- Keep short `Trace:` progress lines before meaningful work units.
- Do not expose secrets from runtime files, env files, browser state, or credential stores.
- Do not reset or discard unrelated dirty work. Several repos have generated or shard-owned changes.
- Do not publish builds directly to GitHub. Source/download authority for clients is `chummer.run` only; GitHub should receive source and design changes, not release binaries.
- The Fleet may be running worker shards. Do not interrupt worker loops unless the user explicitly asks for Fleet operations.

## Current Objective

The old UI-side tester-audit blocker is closed. The current blockers have shifted:

- `/docker/chummercomplete/chummer6-ui/.codex-studio/published/USER_JOURNEY_TESTER_AUDIT.generated.json` exists and reports `status: pass`.
- Fleet flagship readiness still warns on `fleet_and_operator_loop`.
- The live reason is runtime healing, not missing desktop proof:
  - `fleet-auditor` is in `escalation_required`
  - runtime-healing summary is `alert_state: action_needed`
- The routed local journey blocker is now stale mobile proof for `install_claim_restore_continue`, not desktop UI.

Operator watcher note (high-priority): the dedicated tester shard is still explicit as `shard-14` in fleet topology. Treat this shard as non-optional in health checks whenever Fleet is running.

## Local Commits Not Yet Pushed

These older push notes are stale.

- `/docker/fleet`: `git rev-list --left-right --count origin/main...HEAD` currently reports `4 3`
- `/docker/chummercomplete/chummer-design`: `git rev-list --left-right --count origin/main...HEAD` currently reports `47 67`

Do not assume the earlier single-commit push instructions are still valid. Re-evaluate branch and landing intent before pushing anything.

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

Observed then:

- Overall readiness: `fail; ready=7, warning=0, missing=1`
- `desktop_client`: `missing`
- Missing all five required tester workflows.
- Missing discipline evidence: `linux_binary_under_test`, `used_internal_apis_false`, `fix_shard_separate_true`.

That observation is no longer current. As of 2026-05-17:

- `/docker/chummercomplete/chummer6-ui/.codex-studio/published/USER_JOURNEY_TESTER_AUDIT.generated.json` exists
- the artifact reports `status: pass`
- all five required workflows are present and passing
- Fleet readiness now fails on `fleet_and_operator_loop`, not the tester audit

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

## Current Gaps

Current audited gaps, in priority order:

1. Fleet operator/runtime healing
   - `fleet-auditor` is escalated and keeps `fleet_and_operator_loop` at warning.
   - See `.codex-studio/published/STATUS_PLANE.generated.yaml`.
2. Mobile journey proof freshness
  - [done] Re-ran `chummer6-mobile` local proof materializer; proof artifact is now regenerated and no longer stale for `install_claim_restore_continue`.
3. Tester-audit evidence quality
  - [done] strengthened validator requires PNG files with real headers and minimum dimensions, and added focused proof-quality tests to reject non-credible placeholder payloads.
3. Scoped failure trace
   - Final fail was caused by feedback-loop/recovery-trust readiness warnings: stale support-case packets and source-mirror mode.
   - Re-ran support-case packet materializer and re-ran readiness probe; both now pass with these warnings resolved.
4. Operator handoff truth
   - This file had drifted badly enough to send work toward already-closed UI blockers.

## Next Concrete Steps

1. Repair Fleet runtime health first.
   - [done] `fleet_and_operator_loop` now has a narrowly scoped stale-supervisor recovery when the only blocker is stale `supervisor_recent_enough` and Fleet/operator signals are otherwise healthy in configured idle topology.
   - Re-run focused readiness materialization and confirm published warning now resolves; if not, escalate next to runtime-healing evidence.
2. Refresh the stale mobile proof.
   - Regenerate `/docker/chummercomplete/chummer6-mobile/.codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json`.
   - Re-run Fleet readiness and confirm `install_claim_restore_continue` no longer contributes a local blocker.
3. Tighten tester-audit evidence quality.
   - [done] Strengthened validator and tests now reject placeholder-like screenshot evidence; no further action is required here unless real artifacts regress.
4. Re-run the focused Fleet readiness probe and confirm the only remaining warnings, if any, are current and intentional.
   - [done] Focused readiness now passes after support packet refresh (`python3 scripts/materialize_flagship_product_readiness.py --out /tmp/FLAGSHIP_PRODUCT_READINESS.audit.json ...`).

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

Probe the current Fleet readiness state without changing published artifacts:

```bash
cd /docker/fleet
python3 scripts/materialize_flagship_product_readiness.py \
  --out /tmp/FLAGSHIP_PRODUCT_READINESS.audit.json \
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
