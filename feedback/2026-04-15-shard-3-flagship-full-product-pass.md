# Shard 3 flagship full-product pass

## Outcome

Repo-local evidence still fails closed only on the external native macOS desktop tuple `avalonia:osx-arm64:macos`.
No publish or readiness mirror refresh is justified until that host proof is recaptured and ingested.

## Evidence checked

- Task-local telemetry still reports one open flagship milestone and outstanding readiness coverage only on `desktop_client`.
- `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json` still reports:
  - `status=fail`
  - `warning_keys=["desktop_client"]`
  - `completion_audit.external_only=true`
  - `completion_audit.unresolved_external_proof_request_tuples=["avalonia:osx-arm64:macos"]`
- `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md` is current for this run and still requests only the macOS tuple above.
- `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json` and the mirrored host-proof bundle receipt both record:
  - `status=pass`
  - `platform=macos`
  - `rid=osx-arm64`
  - `recordedAtUtc=2026-04-11T20:19:47.089302+00:00`
  - matching installer digest `424b3216afedf86347494eea985cc1e7ceca7cb8cbf7aff04a475456a15973f4`
  - but are now stale relative to the 24-hour freshness gate

## Verifier results

- `python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json`
  - pass
- `python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir .codex-studio/published/external-proof-commands`
  - fail only on unresolved external-proof backlog rooted in:
    - host `macos`
    - tuple `avalonia:osx-arm64:macos`
    - release-channel missing required promoted tuple coverage
    - journey rows `install_claim_restore_continue`, `organize_community_and_close_loop`, and `report_cluster_release_notify`
- `python3 scripts/materialize_flagship_product_readiness.py --out /tmp/FLAGSHIP_PRODUCT_READINESS.audit.json --mirror-out /tmp/FLAGSHIP_PRODUCT_READINESS.mirror.json`
  - recomputed audit matches the published closure reason: only external host-proof gaps remain

## Required next step

Run the generated macOS host lane from `/docker/fleet/.codex-studio/published/external-proof-commands/`, capture a fresh native-host startup-smoke receipt for `avalonia:osx-arm64:macos`, ingest the bundle, then republish release truth.
