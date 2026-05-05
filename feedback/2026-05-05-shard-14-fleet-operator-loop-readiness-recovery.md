## Slice

- Recovered `fleet_and_operator_loop` in `scripts/materialize_flagship_product_readiness.py` when the only live blocker is desktop-scoped external host proof and the remaining Fleet warnings are stale operator bookkeeping (`runtime_healing`, external-proof runbook timestamps, or `dispatchable_truth_ready` drift).
- Added a regression in `tests/test_materialize_flagship_product_readiness.py` for the live shape where macOS proof is still outstanding but Fleet control-loop truth should stay `ready`.
- Republished `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`; it now reports `ready_keys` including `fleet_and_operator_loop`, `warning_keys=[]`, and `missing_keys=["desktop_client"]`.

## Remaining blocker

- Published readiness is still correctly fail-closed on the unresolved external tuple `avalonia:osx-arm64:macos`.
- `external_host_proof.reason` still points to the required macOS command pack flow under `/docker/fleet/.codex-studio/published/external-proof-commands/`.
