# EA parity-lab warning sync

## Scope

- `docs/chummer5a-oracle/README.md`
- `docs/chummer5a-oracle/veteran_workflow_packs.yaml`
- `tests/test_ea_parity_lab_capture_pack.py`

## What changed

- Resynced the EA veteran compare pack to the current flagship readiness snapshot in `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`.
- Removed stale `fleet_and_operator_loop` warning coverage from `whole_product_frontier_coverage`; the live warning set is now `desktop_client` only.
- Tightened the desktop frontier blocker text so it points only at the still-unresolved external host tuple `avalonia:osx-arm64:macos` instead of the already-cleared Windows tuple.
- Updated the package README so the tuple-pack description matches the current promoted-proof state.
- Strengthened `tests/test_ea_parity_lab_capture_pack.py` to require exact whole-frontier warning-key parity with live readiness and to fail if the desktop-lane blocker text drifts back to the cleared Windows tuple.

## Verification

- Ran the direct Python harness for `tests/test_ea_parity_lab_capture_pack.py` because `pytest` is not installed in this worker runtime.
- Result: `ALL_PASS 19`.
