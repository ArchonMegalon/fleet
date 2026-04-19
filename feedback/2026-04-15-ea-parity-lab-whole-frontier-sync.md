# EA parity-lab whole-frontier sync

- Resynced `docs/chummer5a-oracle/parity_lab_capture_pack.yaml` and `docs/chummer5a-oracle/veteran_workflow_packs.yaml` to shard-11 run `20260415T004952Z-shard-11` and readiness receipt `2026-04-15T00:49:46Z`.
- Widened `whole_product_frontier_coverage` so the package now records the live flagship warning lanes `hub_and_registry` and `horizons_and_public_surface` alongside the missing `desktop_client` lane instead of flattening the whole frontier down to desktop-only.
- Split promoted desktop tuple compare packs from the currently unresolved external-proof tuple set so the manifests keep the Windows compare pack without falsely reporting it as still unresolved.
- Updated `docs/chummer5a-oracle/README.md` and `tests/test_ea_parity_lab_capture_pack.py` to match the current telemetry, readiness gap set, and tuple-map contract.
