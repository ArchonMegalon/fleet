# Review Template Access Unblock Backlog

Purpose: executable queue work to close WL-D007-01 through WL-D007-06 once sibling-repo `.codex-design/review` writes are restored.

Status key:
- `queued`
- `in_progress`
- `blocked`
- `done`

Dependency:
- sibling-repo `.codex-design/review` writes are restored and verified

| Backlog ID | Status | Task | Owner | Evidence |
|---|---|---|---|---|
| WL-D011-01 | done | Confirm writable access for `.codex-design/review` in `chummer6-core`, `chummer6-ui`, `chummer6-hub`, `chummer6-mobile`, `chummer6-ui-kit`, and `chummer6-hub-registry`; capture each `publish_ref`. | agent | completed on `2026-03-11T23:32:58Z` during review-context republish |
| WL-D011-02 | done | Re-run WL-D007-01..06 publish copies from repo-matched review templates into destination `.codex-design/review/REVIEW_CONTEXT.md`. | agent | completed on `2026-03-11T23:32:58Z` |
| WL-D011-03 | done | Compute source and destination SHA-256 checksums for WL-D007-01..06 and append checksum parity evidence. | agent | completed in `products/chummer/sync/REVIEW_TEMPLATE_MIRROR_PUBLISH_EVIDENCE.md` on `2026-03-11T23:32:58Z` |
| WL-D011-04 | done | Flip WL-D007-01..06 from `blocked` to `done` in `products/chummer/sync/REVIEW_TEMPLATE_MIRROR_BACKLOG.md`; keep WL-D007-07 tied to WL-D010 until media-factory is provisioned. | agent | completed on `2026-03-11T23:32:58Z` |
| WL-D011-05 | done | Update `WORKLIST.md` to reflect WL-D007 narrowed scope and set WL-D011 done after evidence lands, then run `bash scripts/ai/verify.sh`. | agent | completed on `2026-03-11T23:32:58Z` |
