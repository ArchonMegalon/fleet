# Shard 7 macOS proof blocker audit

Date: 2026-04-14
Frontier: `4355602193`
Scope: `Full Chummer5A parity and flagship proof closeout`
Run: `20260414T231929Z-shard-7`

## Result

The flagship frontier still cannot be republished to green from this worker run.
The only remaining blocker is the required native macOS proof tuple:

* `avalonia:osx-arm64:macos`

## Evidence checked

* `/var/lib/codex-fleet/chummer_design_supervisor/shard-7/runs/20260414T231929Z-shard-7/TASK_LOCAL_TELEMETRY.generated.json`
* `/var/lib/codex-fleet/chummer_design_supervisor/shard-7/ACTIVE_RUN_HANDOFF.generated.md`
* `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
* `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
* `/docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh`
* `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos/external-proof-manifest.json`
* `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`

## Findings

1. Published readiness is still fail-closed only on `desktop_client`.
   `FLAGSHIP_PRODUCT_READINESS.generated.json` still reports:
   `Only external host-proof gaps remain: run the missing macos proof lane for 1 desktop tuple(s), ingest receipts, and then republish release truth.`

2. The promoted macOS installer artifact is present and still matches the tuple contract.
   `Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg` hashes to:
   `424b3216afedf86347494eea985cc1e7ceca7cb8cbf7aff04a475456a15973f4`

3. The only available startup-smoke receipt is stale.
   Both the live downloads shelf and the cached host-proof directory carry:
   * `recordedAtUtc: 2026-04-11T20:19:47.089302+00:00`
   * `status: pass`
   * `headId: avalonia`
   * `rid: osx-arm64`

4. The regenerated external-proof runbook now exposes that cached state directly.
   `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md` now shows:
   * `cached_bundle_status: stale_directory`
   * `cached_bundle_archive_path: /docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-bundle.tgz`
   * `cached_bundle_directory_path: /docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos`

5. The published validator still fails only for freshness, not contract shape.
   `./validate-macos-proof.sh` fails with:
   `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=270294:max_age_seconds=86400`

6. No newer local macOS proof bundle or receipt exists in the allowed local state.
   The only macOS receipt visible under the published commands tree and the live UI downloads shelf is the same April 11 capture.

## Conclusion

Do not republish readiness from this worker run.
The local state is now more explicit, but it still does not justify claiming closure.

## Exact next action

Run `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`
on a native macOS host, ingest the resulting fresh bundle, and then run
`/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`.
