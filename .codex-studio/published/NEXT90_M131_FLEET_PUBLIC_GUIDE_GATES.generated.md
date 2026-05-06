# Fleet M131 public-guide gates

- status: pass
- public_guide_gate_status: blocked
- package_id: next90-m131-fleet-verify-public-guide-regeneration-visibility-source-fresh
- frontier_id: 5694544514
- generated_at: 2026-05-06T03:42:57Z

## Runtime summary
- guide_surface_gate_status: blocked
- flagship_queue_status: fail
- flagship_queue_task_count: 1
- guide_repo_head_sha: cb45dcf64ccedc810b16b006bfe500f4253dcbf5
- guide_repo_head_age_hours: 40.35
- runtime_blocker_count: 4
- warning_count: 2

## Package closeout
- state: pass
- warnings:
  - guide_surface_gate: Guide surface verifier blocked regeneration: RuntimeError: UPDATES/README.md is missing required change-log section: Latest substantial pushes
  - flagship_queue_gate: Flagship queue finding: guide_surface_verify:RuntimeError:UPDATES/README.md is missing required change-log section: Latest substantial pushes
  - flagship_queue_gate: Flagship queue finding: story_cast_signature:assets/hero/chummer6-hero.png:solo
  - flagship_queue_gate: Flagship queue finding: story_subject_weak:assets/hero/chummer6-hero.png:2/3
  - Flagship queue cannot burn 1min credits at the current floor (43826189 / 150000000).
  - Guide repo has 12 uncommitted path(s).
