# Shard 5 flagship macOS proof blocker

Date: 2026-04-14
Frontier: `1300044932`
Scope: `Full Chummer5A parity and flagship proof closeout`
Run: `20260414T235905Z-shard-5`

## Result

The flagship frontier still cannot close from this worker run.
The only remaining blocker is the required native macOS desktop tuple:

* `avalonia:osx-arm64:macos`

## Evidence checked

* `/var/lib/codex-fleet/chummer_design_supervisor/shard-5/runs/20260414T235905Z-shard-5/TASK_LOCAL_TELEMETRY.generated.json`
* `/var/lib/codex-fleet/chummer_design_supervisor/shard-5/ACTIVE_RUN_HANDOFF.generated.md`
* `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
* `/docker/fleet/.codex-studio/published/full-product-frontiers/shard-5.generated.yaml`
* `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
* `/docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh`
* `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`
* `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`

## Findings

1. Published readiness is still fail-closed only on `desktop_client`.
   `FLAGSHIP_PRODUCT_READINESS.generated.json` still reports:
   `Only external host-proof gaps remain: run the missing macos proof lane for 1 desktop tuple(s), ingest receipts, and then republish release truth.`

2. Release truth, runbook truth, and task-local telemetry all agree on the same unresolved tuple.
   * task-local telemetry summary still says outstanding readiness coverage is `desktop_client`
   * `RELEASE_CHANNEL.generated.json` still marks `rolloutState: coverage_incomplete`
   * `RELEASE_CHANNEL.generated.json` still marks `missingRequiredPlatformHeadRidTuples: avalonia:osx-arm64:macos`
   * `EXTERNAL_PROOF_RUNBOOK.generated.md` still lists only host `macos` and tuple `avalonia:osx-arm64:macos`
   * `verify_external_proof_closure.py --json` still fails only on the expected external backlog rows rooted in that tuple

3. The promoted macOS installer artifact is present and the proof bundle manifest matches the tuple contract.
   * installer path: `/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg`
   * expected SHA-256: `424b3216afedf86347494eea985cc1e7ceca7cb8cbf7aff04a475456a15973f4`
   * external runbook request count: `1`

4. The available macOS startup-smoke receipt is real but stale for the current release window.
   `Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json` records:
   * `recordedAtUtc: 2026-04-11T20:19:47.089302+00:00`
   * `channelId: preview`
   * `version: run-20260411-201805`
   * `status: pass`

5. This worker can prove the blocker but cannot satisfy it locally.
   * `uname -s && command -v hdiutil || true` returns `Linux` with no `hdiutil`
   * `validate-macos-proof.sh` still fails with:
     `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
   * no repo-local change can convert the current `desktop_client` warning into green without a fresh native macOS capture

## Conclusion

Do not republish readiness from this worker run.
The repo-local evidence still justifies a fail-closed blocker report, not a green claim.

## Exact next action

Run `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`
on a native macOS host with signed-in download auth, ingest the resulting fresh bundle,
and then run
`/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`.
