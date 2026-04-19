# Shard 8 macOS proof blocker audit

Date: 2026-04-14
Frontier: `4575045159`
Scope: `Full Chummer5A parity and flagship proof closeout`
Run: `20260414T230924Z-shard-8`

## Result

The flagship frontier cannot be republished to green from this worker run.
The only remaining blocker is still the required native macOS proof tuple:

* `avalonia:osx-arm64:macos`

## Evidence checked

* `/var/lib/codex-fleet/chummer_design_supervisor/shard-8/runs/20260414T230924Z-shard-8/TASK_LOCAL_TELEMETRY.generated.json`
* `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
* `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
* `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
* `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos/external-proof-manifest.json`
* `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
* `/docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh`
* `python3 /docker/fleet/scripts/verify_external_proof_closure.py --support-packets /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates /docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook /docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir /docker/fleet/.codex-studio/published/external-proof-commands --json`
* `uname -s && command -v hdiutil`

## Findings

1. Published readiness is still fail-closed only on external macOS proof.
   `FLAGSHIP_PRODUCT_READINESS.generated.json` reports `desktop_client` as the lone warning coverage key and says the remaining action is to run the missing macOS proof lane for `avalonia:osx-arm64:macos`.

2. The promoted macOS installer artifact is present locally.
   `Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg` exists and matches the runbook tuple.

3. The available macOS startup-smoke receipt is stale.
   The receipt content records `recordedAtUtc: 2026-04-11T20:19:47.089302+00:00`, which is about `74.87` hours old relative to the current run context and outside the 24-hour freshness window used by the external-proof closure contract.

4. The host-proof bundle currently mirrors that same stale receipt.
   The bundle manifest is shaped correctly for `avalonia:osx-arm64:macos`, but its bundled startup-smoke receipt carries the same April 11 timestamp and therefore cannot justify republishing.

5. The current release channel still honestly reports missing macOS tuple coverage under `desktopTupleCoverage`.
   `RELEASE_CHANNEL.generated.json` still lists:
   * `desktopTupleCoverage.missingRequiredPlatforms`: `macos`
   * `desktopTupleCoverage.missingRequiredPlatformHeadPairs`: `avalonia:macos`
   * `desktopTupleCoverage.missingRequiredPlatformHeadRidTuples`: `avalonia:osx-arm64:macos`

6. External-proof verification still fails for the same reason.
   Running `python3 scripts/verify_external_proof_closure.py ... --json` against the published artifacts fails because support packets, journey gates, and release-channel tuple coverage all still show the unresolved macOS tuple, including:
   * `support packets unresolved_external_proof_request_count=1 (expected 0)`
   * `release channel missingRequiredPlatformHeadRidTuples is not empty: avalonia:osx-arm64:macos`
   * `journey gates blocked_external_only_tuples is not empty: avalonia:osx-arm64:macos`

7. This worker host cannot capture a qualifying replacement receipt.
   `validate-macos-proof.sh` now fails with `startup-smoke-receipt-stale:...:age_seconds=269495:max_age_seconds=86400`, and `uname -s && command -v hdiutil` confirms the host is `Linux` with no `hdiutil` available.

## Conclusion

Do not republish readiness from this worker run.
The repo-local state does not justify refreshing generated release truth yet.

## Exact next action

Run the macOS native-host proof lane again for `avalonia:osx-arm64:macos`, produce a fresh startup-smoke receipt inside the 24-hour contract window, ingest that bundle, and only then rerun the release-truth materialization chain.
