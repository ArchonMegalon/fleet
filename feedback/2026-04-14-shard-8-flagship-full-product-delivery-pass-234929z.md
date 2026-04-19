# Shard 8 flagship full-product delivery pass

Date: 2026-04-14
Run: `20260414T234929Z-shard-8`
Frontier: `4575045159`
Scope: `Full Chummer5A parity and flagship proof closeout`

## Result

The Fleet-side frontier remains honestly blocked only by the external macOS
desktop proof tuple `avalonia:osx-arm64:macos`.
No repo-local release-truth refresh is justified from this Linux worker.

## Evidence checked

* `/var/lib/codex-fleet/chummer_design_supervisor/shard-8/runs/20260414T234929Z-shard-8/TASK_LOCAL_TELEMETRY.generated.json`
* `/var/lib/codex-fleet/chummer_design_supervisor/shard-8/ACTIVE_RUN_HANDOFF.generated.md`
* `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
* `/docker/fleet/.codex-studio/published/full-product-frontiers/shard-8.generated.yaml`
* `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
* `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
* `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`
* `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos/external-proof-manifest.json`

## Commands re-run

* `cd /docker/fleet/.codex-studio/published/external-proof-commands && ./validate-macos-proof.sh`
  * failed with `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=271946:max_age_seconds=86400`
* `cd /docker/fleet && python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir .codex-studio/published/external-proof-commands --json`
  * failed only on the unresolved external backlog rooted in `avalonia:osx-arm64:macos`, including release-channel missing tuple coverage and journey/support packet backlog rows
* `cd /docker/fleet && python3 scripts/materialize_flagship_product_readiness.py --out /tmp/flagship-product-readiness-shard8-20260414T234929Z.json`
  * succeeded and wrote `fail; ready=7, warning=1, missing=0`

## Current truth

* Task-local telemetry still reports one open, not-started milestone with
  outstanding readiness coverage limited to `desktop_client`.
* Published readiness remains fail-closed with `desktop_client` as the only
  warning coverage key.
* The local macOS receipt still records
  `recordedAtUtc=2026-04-11T20:19:47.089302+00:00`, so the 24-hour external
  proof freshness contract is not satisfied.
* The bundled macOS proof manifest is correctly shaped for the same tuple, but
  the bundled receipt is not fresher than the live UI receipt.
* The required host-lane entrypoint already exists at
  `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`.

## Exact next action

Run the published macOS lane on a native macOS host:

`cd /docker/fleet/.codex-studio/published/external-proof-commands && ./run-macos-proof-lane.sh`

Then ingest and republish release truth:

`cd /docker/fleet/.codex-studio/published/external-proof-commands && ./finalize-external-host-proof.sh`
