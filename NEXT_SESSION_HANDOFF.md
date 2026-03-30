# Next Session Handoff

Date: 2026-03-30
Workspace focus: `/docker/fleet`, `/docker/EA`, `/docker/chummercomplete/*`, `/docker/fleet/repos/*`, `/docker/chummer5a`

## Handoff refresh (2026-03-30T09:35:00+02:00)

- W3 milestone `15` remains the active cross-repo frontier from `chummer-design` (`products/chummer/NEXT_20_BIG_WINS_AFTER_POST_AUDIT_CLOSEOUT_REGISTRY.yaml` still `in_progress`).
- This session materially deepened artifact-shelf and creator-publication posture without treating a clean repo as done:
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
  - `chummer-media-factory` `404c5af` `Anchor creator publication packets to governed status`
    - creator-publication plans now keep the publication id as a first-class packet reference and attachment target.
    - packet evidence is now explicitly labeled for provenance, discovery, ownership, and publication state instead of leaving those semantics implicit.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
- No canon status change was required after these slices; `chummer-design` still correctly leaves milestone `15` as `in_progress`.

## Current pushed baseline

- `chummer.run-services` / `chummer6-hub`: `2de28ebb`
- `chummer-hub-registry`: `e43c71f`
- `chummer6-ui`: `bda91e20`
- `chummer6-mobile`: `4122b34`
- `chummer-design`: `4f93111`
- `EA`: `5a12ca3`
- `chummer6-core`: `572ee12f`
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

4. Media-factory now preserves creator-publication identity and posture inside the packet plan itself.
   Publication packets carry the creator publication id as a governed anchor, and evidence labels explicitly name provenance, discovery, ownership, and state.

5. Downstream hosted smoke now guards the richer registry, publication, and trust-status contract.
   Search/preview smoke covers ownership posture and publication-state carry-through, and hosted publication surfaces are guarded across home and account list/detail views.

## Next likely frontier

Do not reopen the already-landed registry or signed-in-home slices unless a new regression appears.

The next useful re-derivation should come from `chummer-design` and continue W3/W4 depth in the cleanest remaining seams:

- `chummer.run-services` / `chummer6-hub`
  - keep pushing public/account publication and trust posture until milestone `13`, `15`, and `18` are not relying on deeper account-only views or single-card detail paths
- `chummer-media-factory`
  - continue from the now-labeled creator-publication plan by threading those status/trust anchors into any downstream packet/render surfaces that still treat publication posture as implicit
- `chummer6-ui`
  - continue only in clean seams around the existing concurrent Avalonia work; the desktop server-plane adapter is a safer boundary than the in-flight windows

The main rule for the next session is unchanged: re-derive from `chummer-design`, not from the last clean repo boundary.
