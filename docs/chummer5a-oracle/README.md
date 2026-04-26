# Chummer5A Oracle Baselines and Veteran Workflow Packs

This folder closes milestone `103` package `next90-m103-ea-parity-lab` for the EA-owned surfaces:

- `parity_lab:capture`
- `veteran_compare_packs`

## Artifacts

- `parity_lab_capture_pack.yaml`: screenshot baseline capture manifest anchored to Chummer5A source files and oracle inventory, now with line-level source extracts for menu/workbench/master-index/roster landmarks, tuple baseline mapping for desktop-client proof requests, receipt-backed screenshot artifact mapping, and a non-negotiable-to-baseline crosswalk for flagship desktop assertions.
- `veteran_workflow_packs.yaml`: veteran first-minute tasks and parity-family compare packs aligned to flagship parity families, including tuple-level compare packs for the promoted Avalonia Linux, macOS, and Windows desktop routes, visual-familiarity screenshot receipt inventory, explicit workflow maps for build/explain/publish plus import/export round-trip, and a new `veteran_task_compare_packs` crosswalk that ties each first-minute task directly to baseline screenshots and compare artifacts.
- `veteran_workflow_packs.yaml` carries both `task_local_frontier_context` and `whole_product_frontier_coverage`: the first preserves the shard-4 successor-wave assignment context from task-local telemetry, while the second records the current published readiness slice that matters to this oracle pack. It is oracle evidence, not a release certificate.
- Both manifests carry `sync_context` so the package can be audited back to the exact worker-safe telemetry file, embedded task-local telemetry snapshot, Fleet readiness receipt, and UI desktop executable-gate receipt used for this sync.
- The current sync for this run is pinned to shard-4 run `20260423T042213Z-shard-4`, readiness receipt `2026-04-23T04:22:19Z`, shard runtime handoff first output `2026-04-23T04:22:17Z`, and desktop executable-gate receipt `2026-04-22T23:48:17.432738Z`.

## Current Readiness Note

- This folder is an oracle pack, not a completion certificate.
- The latest published readiness proof must be checked separately at `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`.
- At the time of this README refresh, that live proof still keeps `desktop_client` missing and also warns on `mobile_play_shell`, `ui_kit_and_flagship_polish`, and `media_artifacts`.
- The release-facing ledger for what remains below gold now lives in `/docker/fleet/.codex-design/product/WHAT_IS_STILL_BELOW_GOLD.md`.

## Milestone-103 Contract Coverage

- screenshot compare packs: `screenshot_baselines` and `screenshot_artifact_baselines` in `parity_lab_capture_pack.yaml`
- first-minute veteran tasks: `required_first_minute_tasks` in `veteran_workflow_packs.yaml`
- first-minute task-to-baseline crosswalk: `veteran_task_compare_packs` in `veteran_workflow_packs.yaml`
- import/export fixtures: `import_export_fixtures` in `parity_lab_capture_pack.yaml`
- workflow maps: `workflow_maps` in `veteran_workflow_packs.yaml`
- whole-frontier readiness map: `whole_product_frontier_coverage` in `veteran_workflow_packs.yaml`, aligned to the current published readiness receipt for `desktop_client` and `fleet_and_operator_loop`
- task-local frontier context: `task_local_frontier_context` in `veteran_workflow_packs.yaml`
- below-gold release ledger: `/docker/fleet/.codex-design/product/WHAT_IS_STILL_BELOW_GOLD.md`

## Provenance

All extracted evidence references the local Chummer5A oracle repo directly:

- `/docker/chummer5a/docs/PARITY_ORACLE.json`
- `/docker/chummer5a/Chummer/Forms/ChummerMainForm.Designer.cs`
- `/docker/chummer5a/Chummer/Forms/Utility Forms/MasterIndex.Designer.cs`
- `/docker/chummer5a/Chummer/Forms/Utility Forms/CharacterRoster.Designer.cs`

## Scope and Limits

- This package is evidence extraction and comparison-pack authoring inside Fleet/EA boundaries.
- This retry is implementation-only: historical operator status snippets, supervisor status helpers, and supervisor ETA helpers are not valid evidence for this package.
- External desktop host-proof backlog is not EA-owned implementation work; this package only supplies the oracle-backed compare pack needed to review the current promoted tuple coverage and veteran-baseline targets when owner-repo proof drifts.
- The currently published desktop executable gate may fail for owner-repo-local reasons while the whole-product flagship readiness receipt also carries broader product gaps; this package does not collapse those truths together.
- The current task-local telemetry is successor-wave queue context; live readiness and desktop-gate receipts remain the release-facing truth.
- It does not bypass executable desktop gate health requirements or release-channel contract drift in owner repos.
- The worker-safe telemetry snapshot is successor-wave assignment context. Treat the latest published readiness receipt as the current release truth and this package as the oracle pack that supports review.
