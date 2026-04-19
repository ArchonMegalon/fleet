# next90-m103-ea-parity-lab shard-3 191322Z sync

- Resynced `docs/chummer5a-oracle/parity_lab_capture_pack.yaml` and `docs/chummer5a-oracle/veteran_workflow_packs.yaml` to the worker-safe shard-3 telemetry file for run `20260418T191322Z-shard-3`.
- Re-anchored the package to the current successor-wave context instead of the stale shard-5 flagship-closeout context, including the live readiness receipt `2026-04-18T19:13:48Z`, shard runtime handoff first output `2026-04-18T19:13:36Z`, and desktop executable-gate receipt `2026-04-18T18:19:11.035798Z`.
- Added `veteran_task_compare_packs` so each first-minute veteran task now points directly at required baseline screenshots, landmarks, and compare artifacts from the Chummer5a oracle pack.
- Updated `tests/test_ea_parity_lab_capture_pack.py` so the verifier derives the active handoff from the synced telemetry path, checks the successor-wave snapshot dynamically, and validates the new first-minute task crosswalk.
