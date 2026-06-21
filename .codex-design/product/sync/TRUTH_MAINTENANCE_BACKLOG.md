# Split-Wave Truth Maintenance Backlog

Purpose: executable backlog for WL-D009/WL-D013 recurring cycles that keep ownership matrix, contract canon, blockers, and milestone truth current during the Chummer split wave.

Status key:
- `queued`
- `in_progress`
- `blocked`
- `done`

Execution scope:
1. Verify package and ownership boundaries stay aligned with split-wave repo boundaries.
2. Keep blocker and milestone truth synchronized with current queue state.
3. Publish dated evidence for every maintenance cycle, including explicit no-change runs.
4. Keep this table cycle-runnable (`queued` baseline); record per-cycle completion in the maintenance log.

| Backlog ID | Status | Scope | Canonical Files | Evidence |
|---|---|---|---|---|
| WL-D009-01 | queued | Start maintenance cycle and record cycle date + operator. | `products/chummer/maintenance/TRUTH_MAINTENANCE_LOG.md` | dated cycle header |
| WL-D009-02 | queued | Reconcile ownership drift against active repo boundaries and forbidden dependencies. | `products/chummer/OWNERSHIP_MATRIX.md` | changed sections or explicit no-change note |
| WL-D009-03 | queued | Reconcile contract family ownership, package ids, and dependency boundaries. | `products/chummer/CONTRACT_SETS.yaml` | changed rows or explicit no-change note |
| WL-D009-04 | queued | Reconcile cross-repo blockers and ensure blocker ownership/status is current. | `products/chummer/GROUP_BLOCKERS.md` | changed blockers or explicit no-change note |
| WL-D009-05 | queued | Reconcile phase/milestone status, exit criteria coverage, current release blockers, and refresh `last_reviewed`. | `products/chummer/PROGRAM_MILESTONES.yaml` | updated `last_reviewed` + changed/no-change note |
| WL-D009-06 | queued | Verify WL-D009/WL-D013 remains represented by current milestone-truth coverage and executable backlog references. | `WORKLIST.md`, `products/chummer/PROGRAM_MILESTONES.yaml` | coverage + reference check note |
| WL-D009-07 | queued | Close cycle with dated delta summary and next-cycle follow-up hooks. | `products/chummer/maintenance/TRUTH_MAINTENANCE_LOG.md` | summary entry with follow-ups |

Completion gate:
1. Every WL-D009 row has a dated per-cycle outcome recorded in the maintenance log; backlog rows remain `queued` as the recurring baseline unless a standing blocker must be marked `blocked`.
2. Each canonical file has either a committed change or an explicit no-change confirmation in the cycle log.
3. `PROGRAM_MILESTONES.yaml` `last_reviewed` reflects the completed maintenance cycle date.
4. Queue/worklist references still point at this backlog and remain executable.
