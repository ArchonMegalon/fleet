# NEXT90 M143 EA route-specific compare packets refresh

Refreshed the EA-owned M143 route-specific compare packet against the active shard-14 runtime handoff so the proof shelf now cites the current run instead of the prior `20260505T235759Z-shard-14` snapshot.

- reran `python3 /docker/fleet/scripts/materialize_next90_m143_ea_route_specific_compare_packets.py`, which repointed `docs/chummer5a-oracle/m143_route_specific_compare_packets.yaml` to `20260506T005401Z-shard-14` and refreshed the paired markdown summary
- reran `python3 /docker/fleet/scripts/verify_next90_m143_ea_route_specific_compare_packets.py --json`; the verifier now passes after the packet refresh
- reran `python3 -m unittest /docker/fleet/tests/test_materialize_next90_m143_ea_route_specific_compare_packets.py /docker/fleet/tests/test_verify_next90_m143_ea_route_specific_compare_packets.py`; both packet guard suites pass
- kept the readiness truth honest: the packet still reports `desktop_client` as `warning`, and the whole-product readiness plane still fails outside this EA proof-authoring slice

The shipped proof remains the same surface slice:

- `sheet_export_print_viewer_and_exchange` stays grounded in exact menu-route receipts, screenshot markers, and workspace-exchange output tokens
- `sr6_supplements_designers_and_house_rules` stays grounded in SR6 successor receipts, rule-environment studio surface proof, and screenshot review markers
