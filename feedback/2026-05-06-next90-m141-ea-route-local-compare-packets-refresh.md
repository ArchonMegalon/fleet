# NEXT90 M141 EA route-local compare packets refresh

Refreshed the EA-owned M141 packet to the current shard-5 worker tuple so the route-local screenshot and compare bundle stays aligned with the live proof inputs instead of the prior run snapshot.

Landed proof shape:
- `docs/chummer5a-oracle/m141_import_route_compare_packets.yaml` now binds the package to shard-5 run `20260506T000258Z-shard-5`, frontier `2841916304`, the live readiness receipt `2026-05-05T23:58:17Z`, and the refreshed desktop-visual receipt `2026-05-06T00:00:28.536600Z`.
- `docs/chummer5a-oracle/m141_import_route_compare_packets.md` was regenerated from the same payload so the machine-readable packet and human summary stay in lockstep.
- `docs/chummer5a-oracle/README.md` now cites the same active M141 proof tuple instead of the older shard-5 run reference.

Verification:
- `python3 scripts/verify_next90_m141_ea_route_local_compare_packets.py --json`
- `python3 -m unittest tests/test_next90_m141_ea_route_local_compare_packets.py`

This refresh keeps the EA-owned proof pack honest. The live flagship readiness receipt still carries `desktop_client` as a warning coverage key, so owner-repo desktop proof drift remains the release blocker outside this package.
