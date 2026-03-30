# Next Session Handoff

Date: 2026-03-30
Workspace focus: `/docker/fleet`, `/docker/EA`, `/docker/chummercomplete/*`, `/docker/fleet/repos/*`, `/docker/chummer5a`

## Handoff refresh (2026-03-30T11:25:00+02:00)

- W3 milestone `15` remains the active cross-repo frontier from `chummer-design` (`products/chummer/NEXT_20_BIG_WINS_AFTER_POST_AUDIT_CLOSEOUT_REGISTRY.yaml` still `in_progress`).
- This session materially deepened artifact-shelf and creator-publication posture without treating a clean repo as done:
  - `chummer6-core` `07f3ba8e` `Deepen starter build kit handoff guidance`
    - starter build kits now project first-playable-session and starter-lane guidance directly in the core hub catalog and install-preview seams instead of leaving onboarding promise implicit in copy.
    - `HubCatalogServiceTests` and `HubInstallPreviewServiceTests` now guard the new first-session/campaign-ready starter guidance.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer-hub-registry` `e43c71f` `Deepen artifact shelf publication posture`
    - `RegistrySearchItem`, `RegistryPreviewResponse`, and `RegistryProjectionResponse` now carry explicit `ShelfOwnershipSummary` plus latest-publication id/state/next-safe-action/trust-band posture.
    - Search and preview endpoints now decorate publication posture the same way projections already did.
    - Owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer.run-services` / `chummer6-hub` `830e9dfc` `Promote artifact shelf posture on home`
    - signed-in home aftermath card now shows ownership and publication state directly on the recap shelf lane, not only audience/publication summary/next step.
    - downstream smoke now exercises the richer registry search/preview contract.
  - `chummer.run-services` / `chummer6-hub` `3e6b2b1d` `Enrich creator publication posture on home`
    - signed-in home creator-publication card now shows discovery posture and humanized publication status in addition to trust/next step/return/support.
    - hosted verification and smoke stayed green after the view upgrade.
  - `chummer.run-services` / `chummer6-hub` `dbbc6221` `Expose publication state in account list`
    - account creator-publication list rows now humanize publication state instead of hiding status only in the selected detail card.
    - hosted verification and smoke stayed green after the list-view update.
  - `chummer.run-services` / `chummer6-hub` `d3d495bd` `Link home publication status back to build path`
    - signed-in home publication cards now keep a title-specific route back to the related build handoff when a governed build path exists.
    - hosted verification and smoke stayed green after the follow-through link update.
  - `chummer.run-services` / `chummer6-hub` `9ccbdca5` `Link account publication list back to build paths`
    - account creator-publication list rows now keep the same title-specific route back to the related build handoff, matching home and detail surfaces.
    - hosted verification and smoke stayed green after the list follow-through link update.
  - `chummer.run-services` / `chummer6-hub` `2de28ebb` `Deepen install-specific trust status`
    - signed-in trust panels on downloads/help/now now expose explicit per-install fix availability and current-caution rows instead of leaving that status implicit in prose.
    - verification-ready linked installs now lower the caution lane while still keeping the direct verify-fix action intact.
    - hosted verification and smoke stayed green after the install-specific trust upgrade.
  - `chummer.run-services` / `chummer6-hub` `227cf097` `Expose adoption health in signed-in trust panels`
    - signed-in trust panels on downloads/help/now/help-trust now carry adoption health alongside install-specific status, so milestone `18` no longer relies on the weekly pulse card alone for measured-adoption posture.
    - smoke now asserts the adoption-health row inside the signed-in trust panel on downloads, help, and now.
    - note: live `main` already advanced further to `6a18dce2` after this slice; the repo is clean at that later head.
  - `chummer-media-factory` `404c5af` `Anchor creator publication packets to governed status`
    - creator-publication plans now keep the publication id as a first-class packet reference and attachment target.
    - packet evidence is now explicitly labeled for provenance, discovery, ownership, and publication state instead of leaving those semantics implicit.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer6-mobile` `dd77e83` `Surface explicit mobile caution posture`
    - workspace-lite projection now exposes an explicit current-caution lane and threads it into follow-through labels, so mobile trust posture is not hidden behind support-next-action prose.
    - ready bundles now lower the caution lane explicitly, while cache pressure still elevates the caution lane with the correct device-safe action.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
- No canon status change was required after these slices; `chummer-design` still correctly leaves milestone `15` as `in_progress`.

## Current pushed baseline

- `chummer.run-services` / `chummer6-hub`: `6a18dce2`
- `chummer-hub-registry`: `e43c71f`
- `chummer6-ui`: `bda91e20`
- `chummer6-mobile`: `dd77e83`
- `chummer-design`: `4f93111`
- `EA`: `5a12ca3`
- `chummer6-core`: `07f3ba8e`
- `chummer-ui-kit`: `f5c49c7`
- `chummer-media-factory`: `404c5af`

## Repo state snapshot

Clean now:

- `/docker/fleet`
- `/docker/EA`
- `/docker/chummercomplete/chummer.run-services`
- `/docker/chummercomplete/chummer-hub-registry`
- `/docker/chummercomplete/chummer6-mobile`
- `/docker/chummercomplete/chummer6-core`
- `/docker/chummercomplete/chummer-ui-kit`
- `/docker/fleet/repos/chummer-media-factory`

Concurrent unrelated dirt intentionally left in place:

- `/docker/chummercomplete/chummer6-ui`
  - multiple Avalonia/runtime/install-linking files plus untracked `DesktopReportIssueWindow.cs`, `DesktopSupportWindow.cs`, `DesktopUpdateWindow.cs`
- `/docker/chummercomplete/chummer-design`
  - large public-guide editorial/asset refresh in progress plus untracked `products/chummer/public-guide-curated-assets/source-plates/horizons/` and `.../parts/`

## Verification completed in this session

- `chummer-hub-registry`
  - `bash scripts/ai/verify.sh`
  - `git diff --check`
- `chummer.run-services`
  - `bash scripts/ai/run_services_verification.sh`
  - `bash scripts/ai/run_services_smoke.sh`
  - targeted `git diff --check` on touched files
- `chummer6-core`
  - `bash scripts/ai/verify.sh`
  - `git diff --check`
- `chummer6-mobile`
  - `bash scripts/ai/with-package-plane.sh build src/Chummer.Play.Core/Chummer.Play.Core.csproj --nologo`
  - `bash scripts/ai/verify.sh`
  - `git diff --check`
- `chummer-media-factory`
  - `bash scripts/ai/verify.sh`
  - `git diff --check`

## What changed materially

1. Registry artifact truth is now explainable on every main read model.
   Search, preview, and projection all expose audience, ownership posture, latest publication state, latest publication trust band, and latest next safe action from one artifact record.

2. Hosted publication surfaces are materially more consistent.
   Signed-in home now exposes aftermath ownership plus publication state, creator-publication discovery plus status, and a direct route back to the related build path, while the account publication list now shows both publication state and the same build-follow-through route instead of forcing detail-card hops.

3. Install-specific trust status is more explicit on signed-in trust surfaces.
   Downloads, help, and now all expose per-install fix availability plus a current-caution row, and the caution lane now de-escalates automatically once the linked install reaches the verification-ready build.

4. Signed-in trust panels now carry measured adoption posture, not only weekly-pulse context.
   Downloads, help, and now surface adoption health inside the install-specific trust panel, so “what is fixed, who can get it now, what is recommended, and what still needs caution” lives beside measured adoption evidence instead of depending on a separate card.

5. Starter build kits now carry grounded first-session guidance from core, and mobile trust posture now has an explicit caution lane.
   Core build-kit details/install previews now describe how starter lanes reach the first playable session and return safely into campaign continuity, while mobile workspace-lite surfaces explicitly state the current caution lane instead of implying it through support prose alone.

6. Media-factory now preserves creator-publication identity and posture inside the packet plan itself.
   Publication packets carry the creator publication id as a governed anchor, and evidence labels explicitly name provenance, discovery, ownership, and state.

7. Downstream smoke and repo-local verification now guard the richer onboarding, trust, and caution contracts.
   Search/preview smoke covers ownership posture and publication-state carry-through, and hosted publication surfaces are guarded across home and account list/detail views.

## Next likely frontier

Do not reopen the already-landed registry or signed-in-home slices unless a new regression appears.

The next useful re-derivation should come from `chummer-design` and continue W3/W4 depth in the cleanest remaining seams:

- `chummer.run-services` / `chummer6-hub`
  - live `main` is already beyond the adoption-health slice at `6a18dce2`; re-derive from that head and keep pushing public/account publication, trust posture, and first-session follow-through until milestone `13`, `15`, `18`, and `19` do not depend on deeper account-only views or single-card detail paths
- `chummer-media-factory`
  - continue from the now-labeled creator-publication plan by threading those status/trust anchors into any downstream packet/render surfaces that still treat publication posture as implicit
- `chummer6-mobile`
  - the next clean seam is publication/trust carry-through beyond the new caution lane, especially anywhere recap-safe or creator-publication posture still stops at state/next-step without explicit trust ranking
- `chummer6-ui`
  - continue only in clean seams around the existing concurrent Avalonia work; desktop trust/onboarding parity still looks like the safest remaining W4 seam once a clean boundary is identified

The main rule for the next session is unchanged: re-derive from `chummer-design`, not from the last clean repo boundary.
