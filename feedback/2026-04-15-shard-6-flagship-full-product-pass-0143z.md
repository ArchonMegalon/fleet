# Shard 6 flagship full-product delivery pass

Date: 2026-04-15
Frontier: `4182074715`
Scope: `Full Chummer5A parity and flagship proof closeout`
Run: `20260415T014057Z-shard-6`

## Result

The flagship full-product frontier remains fail-closed from this worker run.
The only unresolved readiness coverage key is still `desktop_client`, and the only unresolved promoted external proof tuple is:

* `avalonia:osx-arm64:macos`

## Evidence checked

* `/var/lib/codex-fleet/chummer_design_supervisor/shard-6/runs/20260415T014057Z-shard-6/TASK_LOCAL_TELEMETRY.generated.json`
* `/var/lib/codex-fleet/chummer_design_supervisor/shard-6/ACTIVE_RUN_HANDOFF.generated.md`
* `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
* `/docker/fleet/.codex-studio/published/full-product-frontiers/shard-6.generated.yaml`
* `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
* `/docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh`
* `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`
* `/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`

## Findings

1. Published readiness still fails only on external macOS host proof.
   `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json` generated at `2026-04-15T01:37:36Z` still reports:
   `Only external host-proof gaps remain: run the missing macos proof lane for 1 desktop tuple(s), ingest receipts, and then republish release truth.`

2. A fresh local readiness materialization agrees with the published posture.
   `python3 /docker/fleet/scripts/materialize_flagship_product_readiness.py --out /tmp/flagship-readiness-shard6-current.json` wrote a new snapshot at `2026-04-15T01:43:04Z` with:
   * `status=fail`
   * `ready=7`
   * `warning=1`
   * `missing=0`
   * `warning_keys=[desktop_client]`
   * `completion_audit.external_only=true`
   * `unresolved_external_proof_request_tuples=[avalonia:osx-arm64:macos]`

3. The generated macOS proof lane still fails on stale receipt age alone.
   `bash /docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh` returned:
   `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=278596:max_age_seconds=86400`

4. Whole external-proof closure still collapses to the same unresolved tuple.
   `python3 /docker/fleet/scripts/verify_external_proof_closure.py ... --json` returned `status=failed` with `failure_count=23`, and every failure rolls up to the same unresolved macOS backlog:
   * `support packets unresolved_external_proof_request_count=1`
   * `journey gates blocked_external_only_count=3`
   * `release channel missingRequiredPlatforms is not empty: macos`
   * `release channel missingRequiredPlatformHeadPairs is not empty: avalonia:macos`
   * `release channel missingRequiredPlatformHeadRidTuples is not empty: avalonia:osx-arm64:macos`

5. The repo-local desktop exit gate remains externally blocked only.
   `/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json` is still `status=fail`, but `localBlockingFindings=[]` and `blockedByExternalConstraintsOnly=true`.
   The remaining blockers are the expected macOS promotion and receipt freshness mismatches against the current published release:
   * published release channel `docker`
   * published release version `run-20260414-1836`
   * current receipt `channelId=preview`
   * current receipt `version=run-20260411-201805`
   * current receipt `recordedAtUtc=2026-04-11T20:19:47.089302+00:00`

6. The external-proof pipeline itself is aligned.
   The runbook, host manifest, capture script, ingest script, support packets, journey gates, release-channel coverage, and readiness materializer all point at the same required tuple and do not expose a fleet-side contract drift worth patching from this worker run.

## Conclusion

This worker run does not justify republishing readiness or claiming flagship closeout.
The blocker remains external and singular: a fresh native macOS startup-smoke capture for the promoted Avalonia installer is still missing.

## Exact next action

Run the generated host lane on a native macOS arm64 host, then ingest and republish:

```bash
cd /docker/fleet/.codex-studio/published/external-proof-commands
./run-macos-proof-lane.sh
./finalize-external-host-proof.sh
```
