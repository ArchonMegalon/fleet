# Shard 6 flagship full-product delivery pass

Date: 2026-04-15
Frontier: `4182074715`
Scope: `Full Chummer5A parity and flagship proof closeout`
Run: `20260415T012856Z-shard-6`

## Result

The flagship full-product frontier remains fail-closed from this worker run.
The only unresolved readiness coverage key is still `desktop_client`, and the only unresolved promoted external proof tuple is:

* `avalonia:osx-arm64:macos`

## Evidence checked

* `/var/lib/codex-fleet/chummer_design_supervisor/shard-6/runs/20260415T012856Z-shard-6/TASK_LOCAL_TELEMETRY.generated.json`
* `/var/lib/codex-fleet/chummer_design_supervisor/shard-6/ACTIVE_RUN_HANDOFF.generated.md`
* `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
* `/docker/fleet/.codex-studio/published/full-product-frontiers/shard-6.generated.yaml`
* `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
* `/docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh`
* `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`

## Findings

1. Published readiness still fails only on external macOS host proof.
   `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json` generated at `2026-04-15T01:30:09Z` still reports:
   `Only external host-proof gaps remain: run the missing macos proof lane for 1 desktop tuple(s), ingest receipts, and then republish release truth.`

2. Release-channel truth remains honest and still incomplete for macOS.
   `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json` generated at `2026-04-14T22:45:00Z` is still published for channel `docker`, version `run-20260414-1836`, and still reports:
   * `rolloutState: coverage_incomplete`
   * `supportabilityState: review_required`
   * `missingRequiredPlatforms: macos`
   * `missingRequiredPlatformHeadPairs: avalonia:macos`
   * `missingRequiredPlatformHeadRidTuples: avalonia:osx-arm64:macos`

3. The live macOS startup-smoke receipt is still touched stale proof, not fresh capture.
   The receipt still records:
   * `recordedAtUtc: 2026-04-11T20:19:47.089302+00:00`
   * `version: run-20260411-201805`
   * `channelId: preview`
   * `status: pass`
   * `headId: avalonia`
   * `rid: osx-arm64`
   * `platform: macos`
   * `readyCheckpoint: pre_ui_event_loop`
   * `hostClass: macos-host`

4. Worker-side validation still fails only on that stale receipt.
   `bash /docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh` returns:
   `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=277850:max_age_seconds=86400`

5. Full external-proof closure still fails only on the same macOS tuple backlog and its dependent published rows.
   `python3 /docker/fleet/scripts/verify_external_proof_closure.py --support-packets /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates /docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook /docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir /docker/fleet/.codex-studio/published/external-proof-commands --json` reports:
   * `support packets unresolved_external_proof_request_count=1`
   * `journey gates blocked_external_only_count=3`
   * `release channel missingRequiredPlatforms is not empty: macos`
   * `release channel missingRequiredPlatformHeadPairs is not empty: avalonia:macos`
   * `release channel missingRequiredPlatformHeadRidTuples is not empty: avalonia:osx-arm64:macos`

## Conclusion

This worker run does not justify republishing readiness or claiming flagship closeout.
The blocker is still external and specific: a fresh native macOS startup-smoke capture for the promoted Avalonia installer is missing.

## Exact next action

Run the generated host lane on a native macOS host, then ingest and republish:

```bash
cd /docker/fleet/.codex-studio/published/external-proof-commands
./run-macos-proof-lane.sh
./finalize-external-host-proof.sh
```
