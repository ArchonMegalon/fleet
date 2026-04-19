# Shard 8 flagship desktop proof audit

## Scope

- Frontier: `4575045159` (`flagship_product`)
- Focus: flagship closeout, horizons/public posture, desktop-client proof
- Run: `20260414T230924Z-shard-8`
- Worker host: Linux-only

## What I verified

- Read the worker-safe telemetry, active run handoff, flagship readiness, frontier snapshot, and required Chummer design canon files.
- Re-read the published external-proof runbook and host command scripts for the remaining macOS tuple.
- Verified the current macOS startup-smoke receipt at `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`.
- Ran the published macOS proof validator and external-proof closure verifier directly against the live repo state.

## Current result

- `FLAGSHIP_PRODUCT_READINESS.generated.json` remains correctly fail-closed on `desktop_client` only.
- `completion_audit.external_only=true` remains accurate.
- The only unresolved promoted external tuple is `avalonia:osx-arm64:macos`.
- The current macOS receipt still records `recordedAtUtc=2026-04-11T20:19:47.089302+00:00`, which is about `74.87` hours old and stale against the 24-hour proof contract.
- The live release channel still marks tuple coverage incomplete under `desktopTupleCoverage`, including `missingRequiredPlatformHeadRidTuples=["avalonia:osx-arm64:macos"]`.

## Command results

- `cd /docker/fleet/.codex-studio/published/external-proof-commands && ./validate-macos-proof.sh`
  - failed with `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=269495:max_age_seconds=86400`
- `cd /docker/fleet && python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir .codex-studio/published/external-proof-commands --json`
  - failed only on the expected external backlog rooted in `avalonia:osx-arm64:macos`, including release-channel, support-packet, and journey-gate backlog entries for that tuple
- `uname -s && command -v hdiutil`
  - host is `Linux`; `hdiutil` is unavailable here

## Exact blocker

- This worker host cannot honestly capture the required native macOS installer/startup-smoke proof lane.
- Release truth should not be republished from this host because no new qualifying proof was ingested.
- The next real step is still to run `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh` on a native macOS host, ingest the resulting bundle, and then run the published finalize/republish chain.
