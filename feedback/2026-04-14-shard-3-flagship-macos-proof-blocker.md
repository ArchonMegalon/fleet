# Shard 3 flagship macOS proof blocker

Date: 2026-04-14
Frontier: `2541792707`
Scope: `Full Chummer5A parity and flagship proof closeout`
Run: `20260414T234529Z-shard-3`

## 2026-04-15T00:08Z refresh

Run: `20260414T235942Z-shard-3`

The blocker state did not improve in this pass.
The important new detail is that the local macOS receipt file now has a newer filesystem timestamp, but the receipt payload is still the old proof from `2026-04-11`, so the tuple remains invalid for release-proof closure.

## Result

The flagship frontier still cannot close from this worker run.
The only remaining blocker is the required native macOS desktop tuple:

* `avalonia:osx-arm64:macos`

## Evidence checked

* `/var/lib/codex-fleet/chummer_design_supervisor/shard-3/runs/20260414T234529Z-shard-3/TASK_LOCAL_TELEMETRY.generated.json`
* `/var/lib/codex-fleet/chummer_design_supervisor/shard-3/ACTIVE_RUN_HANDOFF.generated.md`
* `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
* `/docker/fleet/.codex-studio/published/full-product-frontiers/shard-3.generated.yaml`
* `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
* `/docker/fleet/.codex-studio/published/external-proof-commands/preflight-macos-proof.sh`
* `/docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh`
* `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`
* `/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_EXTERNAL_HOST_PROOF_BLOCKERS.generated.json`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`

## Findings

1. Published readiness is still fail-closed only on `desktop_client`.
   `FLAGSHIP_PRODUCT_READINESS.generated.json` still reports:
   `Only external host-proof gaps remain: run the missing macos proof lane for 1 desktop tuple(s), ingest receipts, and then republish release truth.`

2. Release-channel truth and UI blocker truth agree on the same unresolved tuple.
   `RELEASE_CHANNEL.generated.json` still marks:
   * `rolloutState: coverage_incomplete`
   * `missingRequiredPlatformHeadRidTuples: avalonia:osx-arm64:macos`
   `UI_EXTERNAL_HOST_PROOF_BLOCKERS.generated.json` still marks:
   * `status: blocked`
   * `unresolved_tuples: avalonia:osx-arm64:macos`
   * `blockerCodes: receipt_stale, receipt_precedes_release_publication, receipt_channel_mismatch, receipt_version_mismatch`

3. The promoted macOS installer artifact is present and matches contract.
   `Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg` hashes to:
   `424b3216afedf86347494eea985cc1e7ceca7cb8cbf7aff04a475456a15973f4`

4. The available macOS startup-smoke receipt is real but stale for the current release window.
   `Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json` records:
   * `recordedAtUtc: 2026-04-11T20:19:47.089302+00:00`
   * `channelId: preview`
   * `version: run-20260411-201805`
   * `status: pass`

5. The worker can validate the blocker locally but cannot satisfy it locally.
   Running `preflight-macos-proof.sh` from this Linux worker fails with:
   `external-proof-macos-host-missing-hdiutil`
   Running `validate-macos-proof.sh` fails with:
   `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=271675:max_age_seconds=86400`

6. The newer file mtime is not new proof.
   Current filesystem metadata now shows:
   * `mtime: 2026-04-14 20:54:14.042231073 +0000`
   But the receipt body still records:
   * `recordedAtUtc: 2026-04-11T20:19:47.089302+00:00`
   * `version: run-20260411-201805`
   * `channelId: preview`
   Re-running `validate-macos-proof.sh` in the current shard still fails with:
   `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=272535:max_age_seconds=86400`

## Conclusion

Do not republish readiness from this worker run.
The repos already justify a fail-closed blocker report, not a green claim.

## Exact next action

Run `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`
on a native macOS host with signed-in download auth, ingest the resulting fresh bundle,
and then run
`/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`.
