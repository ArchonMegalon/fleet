# Next Session Handoff

Date: 2026-03-30
Workspace focus: `/docker/fleet`, `/docker/EA`, `/docker/chummercomplete/*`, `/docker/fleet/repos/*`, `/docker/chummer5a`

## Handoff refresh (2026-03-30T10:12:17+02:00)

- W3 milestone `15` plus W4 milestones `18`, `19`, and `20` remain active from `chummer-design` (`products/chummer/NEXT_20_BIG_WINS_AFTER_POST_AUDIT_CLOSEOUT_REGISTRY.yaml` still leaves them `in_progress`).
- This session materially deepened artifact-shelf and creator-publication posture without treating a clean repo as done:
  - `chummer6-core` `07f3ba8e` `Deepen starter build kit handoff guidance`
    - starter build kits now project first-playable-session and starter-lane guidance directly in the core hub catalog and install-preview seams instead of leaving onboarding promise implicit in copy.
    - `HubCatalogServiceTests` and `HubInstallPreviewServiceTests` now guard the new first-session/campaign-ready starter guidance.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer-hub-registry` `e43c71f` `Deepen artifact shelf publication posture`
    - `RegistrySearchItem`, `RegistryPreviewResponse`, and `RegistryProjectionResponse` now carry explicit `ShelfOwnershipSummary` plus latest-publication id/state/next-safe-action/trust-band posture.
    - Search and preview endpoints now decorate publication posture the same way projections already did.
    - Owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer-hub-registry` `a1617c8` `Filter publication lists by trust posture`
    - publication list endpoints now support discoverable-only and ranking-band filters, so creator/publication moderation and discovery consumers can query governed trust posture without re-filtering client-side.
    - registry verification now proves discoverable and ranking-band filters across pending-review, published, creator-published, and replacement-advised states.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
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
  - `chummer.run-services` / `chummer6-hub` `88346706` `Deepen first-session onboarding proof`
    - first playable session projections now carry explicit legal-runner, understandable-return, and campaign-ready summaries derived from grounded rule, continuity, restore, and readiness truth instead of leaving milestone `19` dependent on generic summary prose.
    - signed-in home and account work now surface those onboarding-proof seams directly on the first-session card/detail path, while hosted smoke/API checks guard the richer projection contract.
    - note: live `main` already advanced further to `700cf415` after this slice; the repo is clean at that later head.
  - `chummer.run-services` / `chummer6-hub` `24022d0b` `Broaden first-session proof carry-through`
    - the richer first-session proof now reaches the broader shared campaign cards on signed-in home and the shared campaign list on account work, instead of stopping at one lead card and one selected-detail drawer.
    - hosted verification and smoke stayed green after the wider carry-through slice.
  - `chummer.run-services` / `chummer6-hub` `64e28e5a` `Extend first-session proof on account work`
    - selected shared campaign detail on account work now repeats legal-runner, understandable-return, and campaign-ready proof in the calmer selected-workspace summary and server-plane drawers instead of collapsing back to one generic first-session summary.
    - hosted verification and smoke stayed green after the selected-workspace carry-through slice.
  - `chummer.run-services` / `chummer6-hub` `56dd4ae2` `Deepen home first-session proof`
    - public signed-in home shared-campaign cards now surface understandable-return on the broader workspace rail, and the lead first-session card now carries legal-runner, understandable-return, and campaign-ready proof instead of stopping at the kickoff summary.
    - hosted verification and smoke stayed green after the public-home follow-through slice.
  - `chummer.run-services` / `chummer6-hub` `0b7799de` `Project creator publication trust posture`
    - shared creator-publication projections now carry explicit trust-band and discoverability posture, and hosted home/account publication surfaces render that ranking instead of treating publication trust as provenance-only prose.
    - hosted verification and smoke stayed green after the contract-plus-view carry-through slice.
  - `chummer.run-services` / `chummer6-hub` `3cc00e4b` `Carry creator publication trust into recap shelf`
    - recap-shelf entries now carry creator-publication trust band and discoverability directly from the same governed publication posture instead of flattening recap publication down to state-only metadata.
    - hosted verification and smoke stayed green after the recap-shelf contract carry-through slice.
  - `chummer.run-services` / `chummer6-hub` `910efbf1` `Show adoption health on landing trust pulse`
    - the public landing trust pulse now renders adoption health directly instead of leaving that measured-trust row trapped in the model while only recommended/caution prose reached the public page.
    - hosted verification and smoke stayed green after the public trust-surface slice.
  - `chummer.run-services` / `chummer6-hub` `429e5ebc` `Show access posture on landing trust pulse`
    - the public landing trust pulse now also renders the explicit “Who can get it now” row, so public trust no longer hides current access posture behind the model while only recommended/caution prose is visible.
    - hosted verification and smoke stayed green after the public access-posture slice.
  - `chummer-media-factory` `404c5af` `Anchor creator publication packets to governed status`
    - creator-publication plans now keep the publication id as a first-class packet reference and attachment target.
    - packet evidence is now explicitly labeled for provenance, discovery, ownership, and publication state instead of leaving those semantics implicit.
  - `chummer-media-factory` `ad59123` `Label creator publication trust posture`
    - creator-publication packet evidence now labels trust band and discoverability alongside provenance, discovery, ownership, and state, so downstream publication packets preserve trust posture instead of flattening it away.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer6-mobile` `dd77e83` `Surface explicit mobile caution posture`
    - workspace-lite projection now exposes an explicit current-caution lane and threads it into follow-through labels, so mobile trust posture is not hidden behind support-next-action prose.
    - ready bundles now lower the caution lane explicitly, while cache pressure still elevates the caution lane with the correct device-safe action.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer6-mobile` `40bb5ea` `Surface first-session proof on mobile`
    - workspace-lite now exposes explicit legal-runner, understandable-return, and campaign-ready proof derived from grounded runtime, continuity, restore, and readiness posture, and the mobile shell renders that proof directly instead of leaving milestone `19` embodied only on hosted surfaces.
    - mobile verification stayed green after the shell-contract and regression updates.
  - `chummer6-mobile` `635b0aa` `Expose recap trust posture on mobile`
    - workspace-lite recap publication summaries now surface trust ranking and discoverability posture, so mobile no longer treats creator-publication truth as publication-state-only prose on the recap lane.
    - mobile verification stayed green after the projector and regression updates.
- No canon status change was required after these slices; `chummer-design` still correctly leaves milestone `15` as `in_progress`.

## Current pushed baseline

- `chummer.run-services` / `chummer6-hub`: `429e5ebc`
- `chummer-hub-registry`: `a1617c8`
- `chummer6-ui`: `bda91e20`
- `chummer6-mobile`: `635b0aa`
- `chummer-design`: `4f93111`
- `EA`: `5a12ca3`
- `chummer6-core`: `07f3ba8e`
- `chummer-ui-kit`: `f5c49c7`
- `chummer-media-factory`: `ad59123`

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

1. Registry artifact truth is now explainable on every main read model and filterable by governed trust posture.
   Search, preview, and projection all expose audience, ownership posture, latest publication state, latest publication trust band, and latest next safe action from one artifact record, and publication lists can now be filtered directly by discoverable posture or trust band.

2. Hosted publication surfaces are materially more consistent.
   Signed-in home now exposes aftermath ownership plus publication state, creator-publication discovery plus status, and a direct route back to the related build path, while the account publication list now shows both publication state and the same build-follow-through route instead of forcing detail-card hops.

3. Install-specific trust status is more explicit on signed-in trust surfaces.
   Downloads, help, and now all expose per-install fix availability plus a current-caution row, and the caution lane now de-escalates automatically once the linked install reaches the verification-ready build.

4. Public trust posture now says both who can get the build and how adoption is moving, not just recommendation and caution.
   Downloads, help, and now surface adoption health inside the install-specific trust panel, and the public landing trust pulse now renders both adoption health and the explicit “Who can get it now” row instead of leaving those trust signals hidden behind the model.

5. First-session onboarding proof is now materially richer across hosted home and account routes.
   The bounded first playable session projection now exposes legal-runner, understandable-return, and campaign-ready summaries from grounded rule environment, continuity, claimed-device return, and readiness cues, and signed-in home/account surfaces repeat that proof on shared campaign cards, selected-workspace detail, and the calmer lead first-session card instead of forcing users to infer it from one generic summary line.

6. First-session proof and recap publication trust are now embodied on mobile too, not only on hosted surfaces.
   Mobile workspace-lite now renders explicit legal-runner, understandable-return, and campaign-ready proof from the same grounded runtime/continuity/readiness posture, and its recap lane now carries publication trust ranking plus discoverability posture instead of stopping at publication state alone.

7. Starter build kits now carry grounded first-session guidance from core, and mobile trust posture now has an explicit caution lane.
   Core build-kit details/install previews now describe how starter lanes reach the first playable session and return safely into campaign continuity, while mobile workspace-lite surfaces explicitly state the current caution lane instead of implying it through support prose alone.

8. Media-factory now preserves creator-publication identity, trust posture, and governed status inside the packet plan itself.
   Publication packets carry the creator publication id as a governed anchor, and evidence labels explicitly name provenance, trust band, discoverability, discovery, ownership, and state.

9. Downstream smoke and repo-local verification now guard the richer onboarding, trust, and caution contracts.
   Search/preview smoke covers ownership posture and publication-state carry-through, and hosted publication surfaces are guarded across home and account list/detail views.

## Next likely frontier

Do not reopen the already-landed registry or signed-in-home slices unless a new regression appears.

The next useful re-derivation should come from `chummer-design` and continue W3/W4 depth in the cleanest remaining seams:

- `chummer.run-services` / `chummer6-hub`
  - live `main` is now at `429e5ebc`; re-derive from that head and keep pushing public/account publication, trust posture, and first-session follow-through until milestones `15`, `18`, and `19` no longer depend on deeper account-only views or single-card detail paths
  - the cleanest next seam still looks like public/account carry-through for creator-publication and trust posture on routes that still stop at one calmer card or one detail path, especially any surface that still hides recommendation or caution posture behind prose instead of the new trust-band fields
- `chummer-media-factory`
  - continue from `ad59123` by threading the now-labeled creator-publication trust band and discoverability anchors into any downstream packet/render surfaces that still treat publication posture as implicit
- `chummer6-mobile`
  - the next clean seam is publication/trust carry-through beyond the new caution, onboarding, and recap-trust lanes, especially anywhere creator-publication posture still stops at state/next-step without explicit recommendation or caution posture
- `chummer6-ui`
  - continue only in clean seams around the existing concurrent Avalonia work; desktop trust/onboarding parity still looks like the safest remaining W4 seam once a clean boundary is identified

The main rule for the next session is unchanged: re-derive from `chummer-design`, not from the last clean repo boundary.
