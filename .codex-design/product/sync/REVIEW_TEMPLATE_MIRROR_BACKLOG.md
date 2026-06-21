# Review Template Mirror Backlog

Purpose: executable backlog for WL-D007 to mirror review-guidance templates into each code repo under `.codex-design/review/REVIEW_CONTEXT.md`.

Status key:
- `queued`
- `in_progress`
- `blocked`
- `done`

Execution order:
1. chummer6-core
2. chummer6-ui
3. chummer6-hub
4. chummer6-mobile
5. chummer6-ui-kit
6. chummer6-hub-registry
7. chummer6-media-factory

| Backlog ID | Status | Target Repo | Mirror Source (design repo) | Mirror Target (code repo) | Publish Evidence |
|---|---|---|---|---|---|
| WL-D007-01 | done | chummer6-core | `products/chummer/review/core.AGENTS.template.md` | `.codex-design/review/REVIEW_CONTEXT.md` | checksum parity restored on `2026-03-11T23:32:58Z` |
| WL-D007-02 | done | chummer6-ui | `products/chummer/review/ui.AGENTS.template.md` | `.codex-design/review/REVIEW_CONTEXT.md` | checksum parity restored on `2026-03-11T23:32:58Z`; canonical source now uses the `ui` template name. |
| WL-D007-03 | done | chummer6-hub | `products/chummer/review/hub.AGENTS.template.md` | `.codex-design/review/REVIEW_CONTEXT.md` | checksum parity restored on `2026-03-11T23:32:58Z`; canonical source now uses the `hub` template name. |
| WL-D007-04 | done | chummer6-mobile | `products/chummer/review/mobile.AGENTS.template.md` | `.codex-design/review/REVIEW_CONTEXT.md` | checksum parity restored on `2026-03-11T23:32:58Z`; canonical source now uses the `mobile` template name. |
| WL-D007-05 | done | chummer6-ui-kit | `products/chummer/review/ui-kit.AGENTS.template.md` | `.codex-design/review/REVIEW_CONTEXT.md` | checksum parity restored on `2026-03-11T23:32:58Z` |
| WL-D007-06 | done | chummer6-hub-registry | `products/chummer/review/hub-registry.AGENTS.template.md` | `.codex-design/review/REVIEW_CONTEXT.md` | checksum parity restored on `2026-03-11T23:32:58Z` |
| WL-D007-07 | done | chummer6-media-factory | `products/chummer/review/media-factory.AGENTS.template.md` | `.codex-design/review/REVIEW_CONTEXT.md` | checksum parity restored on `2026-03-11T23:32:58Z` |

Completion gate:
1. Each row has publish evidence with date.
2. Mirror target path is present in each destination repo.
3. No repo uses a mismatched review template file.

Current blocker and owner:
- none; WL-D007 is complete as of `2026-03-11T23:32:58Z`.

Unblock queue links:
- WL-D007-01..06: closed via `products/chummer/sync/REVIEW_TEMPLATE_ACCESS_UNBLOCK_BACKLOG.md`
- WL-D007-07: closed via `products/chummer/sync/REVIEW_TEMPLATE_MIRROR_UNBLOCK_BACKLOG.md`

## Drift Follow-up Queue (2026-03-13T15:58:13Z)

Purpose: keep one explicit drift or parity row per repo without reopening completed `WL-D007`/`WL-D010`/`WL-D011` work.

| Backlog ID | Status | Target Repo | Mirror Source (design repo) | Mirror Target (code repo) | Publish Evidence |
|---|---|---|---|---|---|
| WL-D007-DRIFT-2026-03-13-57 | done | chummer6-core | `products/chummer/review/core.AGENTS.template.md` | `/docker/chummercomplete/chummer6-core/.codex-design/review/REVIEW_CONTEXT.md` | Republished on `2026-03-13T17:21:40Z`; checksum parity restored (`24a430ffa62f1c089e1e893b9a0b1c253e1fa9eb3b2d758ce8c1039b3b726ab3`). |
| WL-D007-DRIFT-2026-03-13-58 | done | chummer6-ui | `products/chummer/review/ui.AGENTS.template.md` | `/docker/chummercomplete/chummer6-ui/.codex-design/review/REVIEW_CONTEXT.md` | Revalidated on `2026-03-14T00:35:53Z`; canonical `ui` source and target match (`c9478bcfff2b6cf5c183bb5f38d7e4c739b92bccd971a03a194bd3bad6b14cb6`), so no publish action was required. |
| WL-D007-DRIFT-2026-03-13-59 | done | chummer6-hub | `products/chummer/review/hub.AGENTS.template.md` | `/docker/chummercomplete/chummer6-hub/.codex-design/review/REVIEW_CONTEXT.md` | Republished on `2026-03-14T00:40:17Z`; checksum parity restored (`dd0b5809895c9686ae8bc81a4f819b289fe44d16a3f5e3d89fb1b61f3fd01d3f`). |
| WL-D007-DRIFT-2026-03-13-63 | done | chummer6-mobile | `products/chummer/review/mobile.AGENTS.template.md` | `/docker/chummercomplete/chummer6-mobile/.codex-design/review/REVIEW_CONTEXT.md` | Revalidated on `2026-03-14T00:35:53Z`; canonical `mobile` source and target already match (`b3a4e2b645e07ec1f808ab2609edfc9559b761f71858fcb675c29e73b935c60e`), so no publish action was required. |
| WL-D007-DRIFT-2026-03-13-60 | done | chummer6-ui-kit | `products/chummer/review/ui-kit.AGENTS.template.md` | `/docker/chummercomplete/chummer6-ui-kit/.codex-design/review/REVIEW_CONTEXT.md` | Republished on `2026-03-13T17:21:40Z`; checksum parity restored (`d033775703bb56f5324a67b59eb087981df2a8ae91abc15e05dedc972f8ea9fa`). |
| WL-D007-DRIFT-2026-03-13-61 | done | chummer6-hub-registry | `products/chummer/review/hub-registry.AGENTS.template.md` | `/docker/chummercomplete/chummer6-hub-registry/.codex-design/review/REVIEW_CONTEXT.md` | Revalidated on 2026-03-13: source and target already match (`711b6ad527b08f0230200ec2fc4defdb0aa845aeb5c7268a18b6e1776142ec21`), so no publish action is required. |
| WL-D007-DRIFT-2026-03-13-62 | done | chummer6-media-factory | `products/chummer/review/media-factory.AGENTS.template.md` | `/docker/fleet/repos/chummer6-media-factory/.codex-design/review/REVIEW_CONTEXT.md` | Republished on `2026-03-13T17:21:40Z`; checksum parity restored (`8447017b9ac1a546863fe44aa3d1cc6af7a3f34b46e5826614039a7561caa837`). |

## Recurring Parity Lane (WL-D014)

Purpose: keep review-template mirrors continuously design-aware by running explicit parity checks and republishing only where drift exists.

| Row | Status | Task | Evidence Target |
|---|---|---|---|
| WL-D014-01 | queued | Compute source and destination SHA-256 checksums for all review-template mirror targets listed in WL-D007 canonical rows. | Append next parity cycle block in `products/chummer/sync/REVIEW_TEMPLATE_MIRROR_PUBLISH_EVIDENCE.md`. |
| WL-D014-02 | queued | If any target checksum drifts, republish only drifted repo mirrors to `.codex-design/review/REVIEW_CONTEXT.md` and capture publish refs. | Append drift-only publish evidence with source/target checksums and publish refs. |
| WL-D014-03 | queued | If no drift exists, append an explicit no-change parity cycle note that still records per-repo checksum match. | Append explicit no-change parity evidence for each WL-D007 drift row checked in the cycle. |
| WL-D014-04 | queued | Reflect cycle disposition in `WORKLIST.md` and `products/chummer/PROGRAM_MILESTONES.yaml` without reopening completed WL-D007/WL-D010/WL-D011/WL-D012 rows. | Update recurring-lane status notes in worklist and milestone executable queue for the completed cycle. |

Latest completed cycle reference:
- `2026-03-14T06:54:15Z`: no drift was detected across all checked review-template mirror targets, and explicit no-change parity evidence was appended for each target in `products/chummer/sync/REVIEW_TEMPLATE_MIRROR_PUBLISH_EVIDENCE.md`.
