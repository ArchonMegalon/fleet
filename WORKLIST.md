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
| WL-300 | queued | P0 | Make fleet trust and status publication strictly live-truth so stale aggregate snapshots, poisoned completion receipts, and misleading ETA/currentness states cannot survive into post-client operations. | agent | Post-client week-1 day-1 slice. Acceptance: aggregate status is derived from current shard truth, `worker exit 125` cannot hold the whole fleet in false-fail posture after recovery, and proof/ETA freshness is mechanically visible instead of inferred. |
| WL-301 | queued | P0 | Extract Chummer-specific shard topology, focus heuristics, proof paths, and owner-group routing out of launcher logic into explicit project configuration contracts. | agent | This is the platform cutover from one-off Chummer logic to reusable fleet behavior. Depends on `WL-300` being materially stable first. |
| WL-302 | queued | P1 | Add steady-state fleet operating profiles (`maintenance`, `standard`, `burst`) with explicit shard caps, resource budgets, and safe promotion/demotion rules. | agent | Acceptance: the operator can move between low-noise idle and high-throughput burst modes without hand-editing runtime knobs. Depends on `WL-300` and should reuse the memory-pressure guard rather than replace it. |
| WL-303 | queued | P1 | Promote executable gates, parity proofs, and flagship-readiness materializers into first-class orchestrated jobs with freshness windows, retries, and dependency edges. | agent | Acceptance: proof lanes are explicit jobs with auditable freshness and failure semantics instead of side effects buried inside shard work. Depends on `WL-301`. |
| WL-304 | queued | P1 | Build a compact operator surface for shard mix, queue health, proof freshness, account health, resource pressure, and blocked milestones. | agent | Acceptance: one admin view is enough to answer “what is running, what is blocked, and what will page me next?” Depends on `WL-300` and should consume the new operating-profile/status truth. |
| WL-305 | queued | P1 | Consolidate restart-safe fleet runtime configuration and validate reboot/recovery behavior so policy survives supervisor restarts and host reboots without tribal knowledge. | agent | Acceptance: one documented config surface controls shard topology, resource policy, and queue posture, and a cold restart reproduces the intended state. Depends on `WL-301` and `WL-302`. |
