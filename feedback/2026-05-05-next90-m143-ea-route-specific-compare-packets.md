# NEXT90 M143 EA route-specific compare packets closeout

Closed the EA-owned M143 packet-authoring slice by compiling route-specific compare packs and artifact-proof bundles for `sheet_export_print_viewer_and_exchange` and `sr6_supplements_designers_and_house_rules`.

Refresh on 2026-05-05T23:39Z:
- reran `scripts/materialize_next90_m143_ea_route_specific_compare_packets.py` against the active shard handoff so the packet now matches the live runtime context and published M143 gate inputs again
- reran `scripts/verify_next90_m143_ea_route_specific_compare_packets.py --json` plus the M143 packet unit tests; both now pass after the refresh
- the packet now tracks the newer readiness proof honestly: `desktop_client` is currently a warning coverage key rather than `ready`, while whole-product readiness still fails on the remaining flagship/veteran plane gaps outside the EA packet-authoring slice

Audit repairs included:
- `docs/chummer5a-oracle/m143_route_specific_compare_packets.yaml` and `.md` now bind each M143 family to exact route receipts, screenshot markers, output tokens, and live readiness context instead of leaving the EA surface implicit inside the workflow pack alone
- `scripts/materialize_next90_m143_ea_route_specific_compare_packets.py` plus `scripts/verify_next90_m143_ea_route_specific_compare_packets.py` now regenerate and fail closed on drift for the M143 EA compare-packet summary
- the oracle README now points at the new M143 packet alongside the existing M141 import packet and M142 family-local bundles, while keeping the `desktop_client` readiness gap stated honestly
