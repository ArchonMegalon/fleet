# Review Template Mirror Unblock Backlog

Purpose: executable queue work to close the last WL-D007 gap once `chummer6-media-factory` is provisioned.

Status key:
- `queued`
- `in_progress`
- `blocked`
- `done`

Dependency:
- destination repo checkout exists and is writable by the operator

| Backlog ID | Status | Task | Owner | Evidence |
|---|---|---|---|---|
| WL-D010-01 | done | Verify repo provisioning for `/docker/fleet/repos/chummer6-media-factory` and capture current destination commit as `publish_ref`. | agent | completed on `2026-03-11T23:32:58Z` |
| WL-D010-02 | done | Publish `products/chummer/review/media-factory.AGENTS.template.md` into `/docker/fleet/repos/chummer6-media-factory/.codex-design/review/REVIEW_CONTEXT.md`. | agent | completed on `2026-03-11T23:32:58Z` |
| WL-D010-03 | done | Compute source and destination SHA-256 checksums and append checksum parity evidence for WL-D007-07. | agent | completed in `products/chummer/sync/REVIEW_TEMPLATE_MIRROR_PUBLISH_EVIDENCE.md` on `2026-03-11T23:32:58Z` |
| WL-D010-04 | done | Flip WL-D007-07 status from `blocked` to `done` in `products/chummer/sync/REVIEW_TEMPLATE_MIRROR_BACKLOG.md` and update blocker notes in `WORKLIST.md`. | agent | completed on `2026-03-11T23:32:58Z` |
| WL-D010-05 | done | Re-run local verification script (`bash scripts/ai/verify.sh`) and append dated completion note in `products/chummer/maintenance/TRUTH_MAINTENANCE_LOG.md`. | agent | completed on `2026-03-11T23:32:58Z` |
