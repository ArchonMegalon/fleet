# Fleet M135 design queued coverage

- status: pass
- design_coverage_status: blocked
- package_id: next90-m135-fleet-add-full-design-queued-coverage-verification-mirror-fres
- frontier_id: 7361549676
- generated_at: 2026-05-05T21:38:10Z

## Runtime summary
- source_family_group_count: 18
- queued_work_task_count: 10 / 10
- shipped_work_task_count: 4
- missing_status_plane_project_count: 0
- runtime_blocker_count: 5
- warning_count: 1

## Package closeout
- state: pass
- warnings:
  - queue_coverage_monitor: design coverage ledger task 135.1 is unknown.
  - mirror_freshness_monitor: mirror backlog is missing repo row(s): executive-assistant, fleet
  - mirror_freshness_monitor: mirror evidence is missing repo row(s): executive-assistant, fleet
  - mirror_freshness_monitor: mirror evidence is older than PROGRAM_MILESTONES last_reviewed (2026-03-19T10:59:51Z < 2026-04-22).
  - mirror_freshness_monitor: mirror evidence does not cover the current PROGRAM_MILESTONES checksum.
  - Recurring WL-D018 mirror backlog is still fully queued.
