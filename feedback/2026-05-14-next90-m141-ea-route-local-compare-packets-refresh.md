# NEXT90 M141 EA route-local compare packets refresh

Refreshed the EA-owned M141 packet to the active shard-2 worker context and repaired the packet materializer for the live receipt layout so the route-local screenshot and compare bundle stays aligned with current proof inputs.

Landed proof shape:
- `scripts/materialize_next90_m141_ea_route_local_compare_packets.py` now tolerates the current receipt split where translator and Hero Lab route-local details are sourced from the UI release gate and workflow screenshot coverage instead of the older screenshot-review receipt shape.
- `scripts/materialize_next90_m141_ea_route_local_compare_packets.py` and `scripts/verify_next90_m141_ea_route_local_compare_packets.py` now auto-resolve the newest shard runtime handoff when `--runtime-handoff` is omitted, so the default path no longer drifts back to the stale shard-5 handoff.
- `tests/test_next90_m141_ea_route_local_compare_packets.py` now covers that current receipt layout in addition to the older shard-local fixture shape.
- `docs/chummer5a-oracle/m141_import_route_compare_packets.yaml` now binds the package to shard-2 run `20260514T180532Z-shard-2`, frontier `2841916304`, the live readiness receipt `2026-05-14T18:04:38Z`, screenshot-review receipt `2026-05-14T18:11:44.352608Z`, and UI release receipt `2026-05-14T15:50:13.565788Z`.
- `docs/chummer5a-oracle/m141_import_route_compare_packets.md` and `docs/chummer5a-oracle/README.md` were refreshed from the same proof tuple so the human summary, provenance note, and machine-readable packet stay in lockstep.

Verification:
- `python3 -m unittest tests/test_next90_m141_ea_route_local_compare_packets.py`
- `python3 scripts/verify_next90_m141_ea_route_local_compare_packets.py --artifact docs/chummer5a-oracle/m141_import_route_compare_packets.yaml --markdown-artifact docs/chummer5a-oracle/m141_import_route_compare_packets.md --task-local-telemetry /var/lib/codex-fleet/chummer_design_supervisor/shard-2/runs/20260514T180532Z-shard-2/TASK_LOCAL_TELEMETRY.generated.json --runtime-handoff /var/lib/codex-fleet/chummer_design_supervisor/shard-2/ACTIVE_RUN_HANDOFF.generated.md --json`

The flagship readiness receipt is still not green after this packet refresh. `desktop_client` remains the live missing coverage key in `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`, and the current published blockers are routed local Avalonia desktop-gate failures rather than an unresolved external-host proof lane.
