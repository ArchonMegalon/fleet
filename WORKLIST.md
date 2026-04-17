# Worklist Queue

Purpose: queue the post-client fleet platform work without losing the current flagship closeout overlay.

## Status Keys
- `queued`
- `in_progress`
- `blocked`
- `done`

## Queue
| ID | Status | Priority | Task | Owner | Notes |
|---|---|---|---|---|---|
| WL-300 | done | P0 | Make fleet trust and status publication strictly live-truth so stale aggregate snapshots, poisoned completion receipts, and misleading ETA/currentness states cannot survive into post-client operations. | agent | Shipped: completion audit now keeps receipt failures visible while top-level status and published completion-review frontiers are driven by current live blockers first; aggregate status aliases refresh from live shard truth; operating-profile memory budgets publish explicit currentness. |
| WL-301 | done | P0 | Extract Chummer-specific shard topology, focus heuristics, proof paths, and owner-group routing out of launcher logic into explicit project configuration contracts. | agent | Shipped: `config/projects/fleet.yaml` is now the explicit supervisor contract for shard topology, focus profiles, proof paths, and shard owner/text routing; `run_chummer_design_supervisor.sh` hydrates shard profile/owner/text defaults from that contract while preserving operator env overrides. |
| WL-302 | done | P1 | Add steady-state fleet operating profiles (`maintenance`, `standard`, `burst`) with explicit shard caps, resource budgets, and safe promotion/demotion rules. | agent | Landed in `scripts/chummer_design_supervisor.py`: `--operating-profile`/`CHUMMER_DESIGN_SUPERVISOR_OPERATING_PROFILE` select maintenance, standard, or burst; profile caps and budgets flow through the memory-pressure guard and publish promotion/demotion guidance in the host-memory snapshot. |
| WL-303 | done | P1 | Promote executable gates, parity proofs, and flagship-readiness materializers into first-class orchestrated jobs with freshness windows, retries, and dependency edges. | agent | Shipped: proof lanes now live in `supervisor_contract.proof_jobs` and materialize to `PROOF_ORCHESTRATION.generated.json` with dependency order, retry policy, freshness windows, and output state validation. |
| WL-304 | done | P1 | Build a compact operator surface for shard mix, queue health, proof freshness, account health, resource pressure, and blocked milestones. | agent | Shipped: `/ops/` and `/admin/operator` now render one compact operator surface, `/api/cockpit/operator-surface` exposes the machine-readable contract, and `tests/test_operator_surface.py` proves shard mix, queue health, proof freshness, account health, resource pressure, and blocked frontier/milestone signals are joined. |
| WL-305 | done | P1 | Consolidate restart-safe fleet runtime configuration and validate reboot/recovery behavior so policy survives supervisor restarts and host reboots without tribal knowledge. | agent | Shipped: `config/projects/fleet.yaml` now owns restart-safe topology, state root, resource policy, queue posture, account routing, and worker defaults; `run_chummer_design_supervisor.sh` hydrates those defaults while preserving env overrides; `tests/test_project_policy_contracts.py` validates cold-restart recovery with `CHUMMER_DESIGN_SUPERVISOR_PRINT_RUNTIME_POLICY=1`. |
