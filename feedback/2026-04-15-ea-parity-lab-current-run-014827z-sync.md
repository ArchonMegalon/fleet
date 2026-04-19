# 2026-04-15 EA parity-lab current-run 014827z sync

## What shipped

- Resynced `docs/chummer5a-oracle/parity_lab_capture_pack.yaml` and `docs/chummer5a-oracle/veteran_workflow_packs.yaml` to the active worker-safe telemetry file for shard-11 run `20260415T014827Z-shard-11`.
- Updated `docs/chummer5a-oracle/README.md` so the package-level provenance note names the active shard run, the current readiness receipt at `2026-04-15T01:37:36Z`, the current external proof runbook at `2026-04-15T01:50:12Z`, and the current UI desktop executable-gate receipt at `2026-04-15T01:33:00.845853Z`.
- Kept the package scoped to EA-owned evidence surfaces only: `parity_lab:capture` and `veteran_compare_packs`.

## Verification

- `python3 /docker/fleet/tests/test_ea_parity_lab_capture_pack.py`

## Remaining blocker

- `desktop_client` still fails closed on the same external-only promoted tuple: `avalonia:osx-arm64:macos`.
- The EA package is current, but Fleet cannot republish release truth to green without a fresh native macOS installer proof capture, bundle ingest, and receipt refresh through the external proof lane.
