# Shard 2 flagship macOS proof blocker

Date: 2026-04-14
Frontier: `3449507998`
Scope: `Full Chummer5A parity and flagship proof closeout`

## Result

The flagship frontier still cannot close from this worker run.
The only remaining blocker is the required native macOS desktop tuple:

* `avalonia:osx-arm64:macos`

## Evidence checked

* `/var/lib/codex-fleet/chummer_design_supervisor/shard-2/runs/20260414T230854Z-shard-2/TASK_LOCAL_TELEMETRY.generated.json`
* `/var/lib/codex-fleet/chummer_design_supervisor/shard-2/ACTIVE_RUN_HANDOFF.generated.md`
* `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
* `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
* `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
* `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos/external-proof-manifest.json`
* `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`

## Local verification

1. Published readiness is still fail-closed only on `desktop_client`.
   `FLAGSHIP_PRODUCT_READINESS.generated.json` still reports the completion audit reason:
   `Only external host-proof gaps remain: run the missing macos proof lane for 1 desktop tuple(s), ingest receipts, and then republish release truth.`

2. The promoted macOS installer artifact is present and matches the tuple contract.
   `Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg` exists and hashes to:
   `424b3216afedf86347494eea985cc1e7ceca7cb8cbf7aff04a475456a15973f4`

3. The available macOS startup-smoke receipt is stale.
   `Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json` records:
   * `recordedAtUtc: 2026-04-11T20:19:47.089302+00:00`
   * `status: pass`
   * `headId: avalonia`
   * `rid: osx-arm64`

4. The published validator still fails for freshness, not shape.
   `./validate-macos-proof.sh` fails with:
   `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=269497:max_age_seconds=86400`

5. Release-channel and closure truth remain aligned with that blocker.
   `RELEASE_CHANNEL.generated.json` still reports:
   * `missingRequiredPlatforms: macos`
   * `missingRequiredPlatformHeadPairs: avalonia:macos`
   * `missingRequiredPlatformHeadRidTuples: avalonia:osx-arm64:macos`

6. External-proof closure still fails only on that unresolved tuple.
   `python3 scripts/verify_external_proof_closure.py ... --json` fails because support packets, journey gates, and release-channel tuple coverage all still list the same macOS backlog.

7. This host cannot honestly produce the missing proof.
   `uname -s` returns `Linux`, and `hdiutil` is not available here.

## Conclusion

Do not republish readiness from this worker run.
The repo-local state does not justify refreshing release truth.

## Exact next action

Run `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`
on a native macOS host, ingest the resulting bundle, and then run
`/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`.
