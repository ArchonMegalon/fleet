# Shard-8 flagship full-product delivery pass

Run: `20260415T013056Z-shard-8`
Frontier: `4575045159`
Timestamp: `2026-04-15T01:34:02Z`

## Summary

The repo-local flagship surfaces are still fail-closed only on the promoted native macOS tuple `avalonia:osx-arm64:macos`.
This pass refreshed the published external-proof runbook and flagship readiness mirror so they now match the live external-only blocker shape again.

## Evidence

- `bash /docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh`
  - fail: `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=278003:max_age_seconds=86400`
- `python3 /docker/fleet/scripts/verify_external_proof_closure.py --support-packets /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates /docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook /docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir /docker/fleet/.codex-studio/published/external-proof-commands --json`
  - fail only on the expected external backlog: `macos`, `avalonia:macos`, `avalonia:osx-arm64:macos`
- `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`
  - still reports `rolloutState=coverage_incomplete`
  - still reports `supportabilityState=review_required`
  - still names the missing required promoted tuple `avalonia:osx-arm64:macos`

## Published truth refreshed

- `python3 /docker/fleet/scripts/materialize_external_proof_runbook.py --support-packets /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates /docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --out /docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
- `python3 /docker/fleet/scripts/materialize_flagship_product_readiness.py --out /docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json --mirror-out /docker/fleet/.codex-design/product/FLAGSHIP_PRODUCT_READINESS.generated.json`

The refreshed readiness receipt now records:

- `generated_at=2026-04-15T01:34:02Z`
- `status=fail`
- `ready_keys=[rules_engine_and_import, hub_and_registry, mobile_play_shell, ui_kit_and_flagship_polish, media_artifacts, horizons_and_public_surface, fleet_and_operator_loop]`
- `warning_keys=[desktop_client]`
- `missing_keys=[]`
- `completion_audit.external_only=true`
- `external_host_proof.unresolved_tuples=[avalonia:osx-arm64:macos]`

## Remaining action

Run the generated native macOS host lane:

```bash
cd /docker/fleet/.codex-studio/published/external-proof-commands
./run-macos-proof-lane.sh
./finalize-external-host-proof.sh
```

This worker cannot complete that lane from Linux without fabricating proof.
