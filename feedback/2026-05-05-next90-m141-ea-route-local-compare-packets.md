# NEXT90 M141 EA route-local compare packets

Closed the EA-owned M141 proof-pack slice by compiling direct screenshot packs and compare packets for the translator route, XML amendment editor route, Hero Lab importer route, custom-data/XML bridge family, and legacy-or-adjacent import-oracle family.

Landed proof shape:
- `scripts/materialize_next90_m141_ea_route_local_compare_packets.py` now resolves the active shard run from `ACTIVE_RUN_HANDOFF.generated.md`, binds the packet to the live task-local telemetry file for that run, and projects the current frontier id from the task-local frontier brief instead of pinning stale hand-entered run metadata.
- `scripts/verify_next90_m141_ea_route_local_compare_packets.py` now resolves the same active run when `--task-local-telemetry` is omitted, so verification does not silently drift back to an older shard snapshot.
- `tests/test_next90_m141_ea_route_local_compare_packets.py` now covers both active-run materialization and default verifier behavior against a shard-local handoff fixture.
- `docs/chummer5a-oracle/m141_import_route_compare_packets.yaml` and `docs/chummer5a-oracle/m141_import_route_compare_packets.md` now bind screenshot names, runtime receipt tokens, deterministic core receipt tokens, and legacy source anchors for all five M141 route or family rows against shard-5 run `20260505T235729Z-shard-5`, frontier `2841916304`, and the live readiness receipt generated at `2026-05-05T23:58:17Z`.

Verification:
- `python3 -m unittest tests.test_next90_m141_ea_route_local_compare_packets`
- `python3 scripts/materialize_next90_m141_ea_route_local_compare_packets.py`
- `python3 scripts/verify_next90_m141_ea_route_local_compare_packets.py --json`

This closes the EA proof-pack slice only. The live flagship readiness receipt generated at `2026-05-05T23:58:17Z` still records `desktop_client` as a warning coverage key, so owner-repo desktop proof drift remains release-blocking outside this package.
