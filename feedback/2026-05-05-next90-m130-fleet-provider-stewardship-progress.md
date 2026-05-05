# M130 Fleet provider stewardship progress

Package: `next90-m130-fleet-add-provider-health-credit-runway-kill-switch-fallback-a`
Owned surfaces: `add_provider_health_credit_runway:fleet`

This pass lands the Fleet-owned provider-stewardship monitor packet for milestone `130.2`.

- `scripts/materialize_next90_m130_fleet_provider_stewardship.py` now compiles one package-scoped monitor packet from the canonical successor registry, the Fleet and design queue rows, the external-tools plane, the LTD capability map, the provider-route stewardship canon, the weekly governor packet, and live Fleet admin/provider truth.
- `scripts/verify_next90_m130_fleet_provider_stewardship.py` now recomputes the same contract with default canonical inputs, so the generated packet can be revalidated without rebuilding the source argument list by hand.
- `tests/test_materialize_next90_m130_fleet_provider_stewardship.py` and `tests/test_verify_next90_m130_fleet_provider_stewardship.py` cover the green path, the blocked path when `provider_canary` disappears, verifier drift rejection, and the new loader fallback when host-side admin imports cannot open the Fleet runtime database.

Audit and improvement pass:

- The first live run exposed a real implementation gap: host-side admin imports could fail on `python-multipart` or the Fleet SQLite path before the packet could read live provider truth. The materializer now falls back to an in-container `fleet-admin` cache-only read, which keeps the packet live even when host imports are incomplete.
- The second audit pass exposed a design gap: a live-generated packet was not deterministic to verify later because the verifier had to requery moving runtime truth. The materializer now emits companion snapshots at `.codex-studio/published/NEXT90_M130_FLEET_PROVIDER_STEWARDSHIP.admin_status.generated.json` and `.provider_credit.generated.json`, and the verifier defaults to those snapshots.

Current proof posture from the live packet:

- The package now passes with `12` governed provider-route rows and no closeout blockers.
- The current warnings are operational rather than implementation failures: fallback coverage is still thin on `core`, `core_authority`, `core_booster`, `core_rescue`, and `groundwork`; the weekly governor posture is still `freeze_launch`; rollback remains armed.
- The current credit-runway basis is still estimated rather than actual, and the captured provider-credit snapshot reported no next top-up timestamp. That is runtime truth to improve later, not a missing monitor contract.

Verification:

- `pytest -q /docker/fleet/tests/test_materialize_next90_m130_fleet_provider_stewardship.py /docker/fleet/tests/test_verify_next90_m130_fleet_provider_stewardship.py`
- `python3 /docker/fleet/scripts/materialize_next90_m130_fleet_provider_stewardship.py`
- `python3 /docker/fleet/scripts/verify_next90_m130_fleet_provider_stewardship.py`
