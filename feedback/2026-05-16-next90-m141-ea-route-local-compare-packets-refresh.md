# NEXT90 M141 EA route-local compare packets refresh

Refreshed the EA-owned M141 packet against the active shard-2 worker context and fixed the resolver so the materializer and verifier stay on the assigned worker shard instead of drifting to whichever shard handoff was newest on disk.

Landed proof shape:
- `scripts/materialize_next90_m141_ea_route_local_compare_packets.py` now honors `CHUMMER_DESIGN_SUPERVISOR_TASK_LOCAL_TELEMETRY_PATH` before falling back to the newest shard handoff, and derives the matching shard runtime handoff from that worker-local telemetry path.
- `tests/test_next90_m141_ea_route_local_compare_packets.py` now covers that worker-env override so future reruns fail if the resolver drifts back to another shard.
- `docs/chummer5a-oracle/m141_import_route_compare_packets.yaml` now binds the package to shard-2 run `20260516T161028Z-shard-2`, frontier `2841916304`, screenshot-review receipt `2026-05-16T00:39:39.035167Z`, desktop-visual receipt `2026-05-15T16:06:33.430811Z`, UI release receipt `2026-05-15T16:06:33.154236Z`, and readiness receipt `2026-05-16T16:11:13Z`.
- `docs/chummer5a-oracle/m141_import_route_compare_packets.md` and `docs/chummer5a-oracle/README.md` were refreshed to match the same shard-2 proof tuple and the current release-facing readiness status.

Verification:
- `python3 -m unittest /docker/fleet/tests/test_next90_m141_ea_route_local_compare_packets.py`
- `python3 /docker/fleet/scripts/verify_next90_m141_ea_route_local_compare_packets.py --json`

The current published readiness receipt is green. The shard-2 task-local telemetry still names `fleet_and_operator_loop` as the active worker frontier coverage, but that queue context no longer means the M141 route-local compare packet itself is stale or mismatched.
