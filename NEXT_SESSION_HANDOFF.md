# Next Session Handoff

Date: 2026-03-29
Workspace focus: `/docker/fleet` plus the active Chummer6 repos in `/docker/chummercomplete` and `/docker/fleet/repos`

## Current state

The latest autonomous wave pushed additive Build/Explain, campaign-publication proof, and a canonical public-guide refresh across multiple repos. The work already landed should be treated as baseline, not as an unfinished branch to reopen blindly.

Recently landed and pushed:

- `chummer6-ui` `51772a7a` `Promote canonical front-door artwork`
- `chummer6-mobile` `26008a7` `Refresh design mirror pulse`
- `chummer-core-engine` `ee5f2453` `Refresh design mirror pulse`
- `chummer6-media-factory` `cfe8f3a` `Refresh design mirror pulse`
- `chummer-hub-registry` `6f61775` `Refresh design mirror pulse`
- `chummer.run-services` `bb73789a` `Surface season board and registry posture`
- `chummer6-design` `678aeb3` `Refresh canonical public guide assets`
- `Chummer6` `af6a4e7` `Sync public guide from design`

Media-factory is currently clean again after the latest slice. The new creator-publication proof now carries:

- `handoff.HandoffId` and `handoff.ExplainEntryId` into packet references
- `Next safe action`, `Campaign return`, and `Support closure` evidence lines into publication planning
- publication-projected `NextSafeAction`, `CampaignReturnSummary`, `SupportClosureSummary`, and watchouts even when the explicit handoff record is unavailable
- executable verification in `Chummer.Media.Factory.Runtime.Verify/Program.cs`

Mobile is currently clean again after the latest slice. The new `M12` regression depth now carries:

- explicit workspace-lite regression proof for observer-lane next-safe-action, read-mostly attention posture, and follow-through labels
- explicit workspace-lite regression proof for GM-runboard next-safe-action, quick actions, and continuity-clear attention posture
- refreshed `.codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json`
- refreshed `WORKLIST.md` milestone truth so `M12` now records the new observer/GM workspace-lite coverage and narrower remaining scope

Hub-registry is currently clean again after the latest slice. Publication read models now carry:

- `ModerationTimeline.NextSafeActionSummary` for every lifecycle state from review queue through retained-history moderation
- `TrustProjection` with explicit ranking band, trust summary, discovery posture, lineage summary, and discoverability flag
- artifact shelf posture on search, preview, and projection read models via `Visibility`, `TrustTier`, `ShelfAudience`, and `ShelfSummary`
- artifact-detail projection joins back to the latest publication state, next-safe action, and trust band so downstream surfaces can stay consumer-only
- runtime projection logic that pulls visibility/trust metadata from the canonical artifact store when it exists instead of inventing a second trust surface
- executable verification covering `review-pending`, `approval-backed`, `curated-live`, `replacement-advised`, and `retained-history` publication posture

Core is currently clean again after the latest slice. Build Lab team coverage now carries:

- explicit covered-role and duplicate-role output instead of forcing downstream consumers to reverse-engineer crew posture from overlaps alone
- deterministic `buildlab.team.duplicate-role-tags` diagnostics when the same role is staffed more than once
- summary parameters for `coveredRoleCount` and `duplicateRoleCount`, keeping the optimizer explain surface campaign-aware and localization-ready
- refreshed `Chummer.CoreEngine.Tests` coverage that locks covered-role, duplicate-role, and deterministic diagnostic ordering in place

Run-services is no longer clean. Its current committed `HEAD` is `bb73789a` (`Surface season board and registry posture`), and new additive local edits are present on top. The latest committed continuity/projection work already carries:

- shared `NextSafeAction`, `CampaignReturnSummary`, and `SupportClosureSummary` on `CreatorPublicationProjection`
- campaign-spine projection logic that reuses lead build-handoff continuity instead of dropping it
- account and signed-in home surfaces that render creator-publication next-step, return, and support truth directly from the shared projection
- shared `BuildHandoffId` on creator-publication follow-through plus an account detail link back to the related build path
- multi-campaign `SeasonBoardEntries` on `CommunityOperatorProjection`, derived directly from shared campaign workspace state
- signed-in home, account work, and live-audit surfaces that bind the new season-board projection instead of inventing a second organizer rail
- downstream smoke and backup/restore verification that lock registry shelf posture, latest publication posture, and operator season-board continuity in place

Media-factory verification that passed for `fdc15c4`:

- `bash scripts/ai/verify.sh`
- `git diff --check`

Additional verification completed after the prior handoff refresh:

- `chummer-core-engine`: `bash scripts/ai/verify.sh`, `git diff --check`
- `chummer6-design`: `bash scripts/ai/verify.sh`, `git diff --check`
- `chummer-hub-registry`: `bash scripts/ai/verify.sh`, `git diff --check`
- `Chummer6`: `bash scripts/verify_public_guide.sh`, `git diff --check`
- `chummer6-ui`: `bash scripts/ai/verify.sh`, `git diff --check`
- `chummer6-mobile`: `bash scripts/ai/verify.sh`, `git diff --check`
- `chummer.run-services`: `bash scripts/ai/run_services_verification.sh`, `bash scripts/ai/run_services_smoke.sh`, `git diff --check`
- `chummer6-media-factory`: `bash scripts/ai/verify.sh`, `git diff --check`

## Concurrent local changes to respect

These were present in the workspace and were intentionally left alone:

- `chummer.run-services`: dirty `.codex-design/product/NEXT_20_BIG_WINS_AFTER_POST_AUDIT_CLOSEOUT_REGISTRY.yaml`, `.codex-design/product/WEEKLY_PRODUCT_PULSE.generated.json`, `Chummer.Run.Api/Services/Community/CampaignSpineService.cs`, `Chummer.Run.Api/Views/PublicLanding/Home.cshtml`, `NEXT_SESSION_HANDOFF.md`, and `scripts/hub-live-audit.py`
- `/docker/EA`: dirty provider/browseract/public-guide-related files on `main`

Do not revert those edits unless a future slice proves they are directly blocking and safe to reconcile.

## What is safe to assume

- The recent Build Lab / campaign OS continuity slices in UI, mobile, core, and media-factory are already landed and pushed.
- The design mirror/public-guide wave is also landed and pushed: canonical design assets and bundle logic changed in `chummer6-design`, the public `Chummer6` repo was re-synced from that bundle, and the repo-local design mirrors in UI/mobile/core/hub-registry/media-factory were refreshed to match.
- The media-factory creator-publication planner now preserves continuity from either the explicit Build Lab handoff or the richer creator-publication projection itself, with verification coverage for both paths.
- Run-services now preserves that creator-publication continuity on the signed-in API and MVC surfaces instead of reducing publication status to trust/discovery/status only, and it keeps a direct link back to the related build path.
- Run-services community-operator projections now expose a first-class multi-campaign season board, and the signed-in home/account/audit surfaces bind it directly from the shared campaign spine.
- Hub-registry publication read models now expose explicit moderation next steps, explicit trust/discovery/lineage posture, explicit artifact shelf posture, and the latest publication state/trust band directly on artifact detail projections.
- Mobile workspace-lite coverage now includes observer and GM role-depth assertions, not just player-lane continuity proof.
- Core Build Lab team coverage now exposes which required roles are already covered and which role tags are duplicated, with deterministic duplicate-role diagnostics and explain parameters.
- Core compatibility matrices now carry the BuildKit next-safe-action inside the session-runtime handoff notes, and UI has regression proof that the HTTP compatibility fallback preserves that text into desktop build previews.
- Hub-registry canonical release-channel materialization now preserves embedded `releaseProof` when regenerating from an existing manifest and emits explicit non-null artifact/runtime compatibility state instead of leaving release truth partially null.
- The year-end milestone set is still materially unfinished across the broader program; there is no honest basis to treat the design as complete.
- The next session should start from live repo evidence, not from a stale assumption that the just-landed slices are still pending.

## Next useful slices

Only start one after rechecking the live repo state:

1. Start with `chummer.run-services`, because it is now the only active Chummer6 repo left dirty in this workspace and the current edits already line up with the season-board/public-guide wave.
2. Extend end-to-end proof where the new Build Lab handoff state still fails to surface in downstream registry/publication or support flows, especially in hosted/community surfaces that still rely on fallback or partially bound customer copy.
3. Refresh generated fleet mirrors and handoff artifacts after each landed canonical-design slice so the next session does not reopen already-synced public-guide work.

## Resume posture

Start with repo status plus targeted verification, then select the highest-impact clean slice. Do not resume quartermaster/controller work unless fresh evidence makes it the top gap again.
