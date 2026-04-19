# Shard 8 flagship current macOS proof status

Date: 2026-04-15
Run: `20260414T235924Z-shard-8`
Frontier: `4575045159`
Scope: `Full Chummer5A parity and flagship proof closeout`

## Summary

The flagship frontier is still blocked only by the external macOS proof tuple
`avalonia:osx-arm64:macos`.
Repo-local release truth is already fail-closed and should not be republished
from this Linux worker.

## Evidence

* Task-local telemetry still reports one open, not-started milestone with
  outstanding readiness coverage limited to `desktop_client`.
* `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
  is still `fail`, with `desktop_client` as the only warning coverage key.
* `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
  still requests only `avalonia:osx-arm64:macos`.
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
  is present but records `recordedAtUtc=2026-04-11T20:19:47.089302+00:00`.
* `cd /docker/fleet/.codex-studio/published/external-proof-commands && ./validate-macos-proof.sh`
  fails with:
  `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=272502:max_age_seconds=86400`
* `python3 /docker/fleet/scripts/verify_external_proof_closure.py --support-packets /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates /docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook /docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir /docker/fleet/.codex-studio/published/external-proof-commands --json`
  fails only on the expected external backlog, including
  `missingRequiredPlatforms=["macos"]`,
  `missingRequiredPlatformHeadPairs=["avalonia:macos"]`, and
  `missingRequiredPlatformHeadRidTuples=["avalonia:osx-arm64:macos"]`.
* `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`
  remains `published` but `rolloutState=coverage_incomplete`,
  `supportabilityState=review_required`, and still lists the same required
  tuple gap `avalonia:osx-arm64:macos`.
* `uname -s && command -v hdiutil || true` returns `Linux` with no `hdiutil`,
  so this worker cannot capture a qualifying macOS receipt.
* `python3 -m pytest /docker/fleet/tests/test_verify_external_proof_closure.py /docker/fleet/tests/test_materialize_external_proof_runbook.py /docker/fleet/tests/test_materialize_flagship_product_readiness.py -q`
  could not be rerun in this worker because `/usr/local/bin/python3: No module named pytest`.

## Release-truth implications

* Do not rerun the republish chain from this worker.
* Do not update published readiness to green or warning-free.
* Keep `desktop_client` as the only open flagship coverage gap until a native
  macOS host captures and ingests a fresh startup-smoke receipt for
  `avalonia:osx-arm64:macos`.

## Exact next action

Run `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`
on a native macOS host, ingest the resulting bundle, then run
`/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`
to republish release truth.
