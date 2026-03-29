# Next Session Handoff

Date: 2026-03-29
Workspace focus: `/docker/fleet`, `/docker/chummer5a`, plus the active Chummer6 repos in `/docker/chummercomplete` and `/docker/fleet/repos`

## Current state

The latest autonomous wave pushed additive Build/Explain depth, organizer guidance, campaign-publication proof, desktop/mobile follow-through clarity, and a canonical public-guide refresh across multiple repos. The work already landed should be treated as baseline, not as an unfinished branch to reopen blindly.

Most recent landed and pushed continuity slices:

- `chummer-core-engine` `09a6ba40` `Deepen build lab progression planner receipts`
- `chummer6-ui` `ab072b12` `Render build lab timeline badges in shared panel`
- `chummer6-ui` `0323f814` `Bind desktop home follow-through labels to next actions`
- `chummer.run-services` `722c0031` `Add campaign memory workspace projections`
- `chummer.run-services` `cf478143` `Thread campaign memory into season board`
- `chummer.run-services` `d8efe52c` `Expose memory return on operator card`
- `chummer.run-services` `49efa728` `Add consequence summaries to season board`
- `chummer.run-services` `1c03bb2e` `Add recap summaries to season board`
- `chummer6-ui` `65e1c638` `Preserve campaign memory on desktop home`
- `chummer6-mobile` `47d3875` `Surface campaign memory in play shell`
- `chummer6-mobile` `b9bb883` `Bind mobile follow-through links to live action copy`
- `chummer6-mobile` `d62610b` `Contextualize mobile cache-pressure decision notices`

Those commits now form the live W1 continuity baseline for long-lived campaign memory plus consequence/recap follow-through across hosted workspace/detail/home surfaces, the operator season board, desktop home, and the mobile play shell. Future work should build on them rather than recreating one-off continuity summaries in downstream heads.

Recently landed and pushed:

- `chummer-core-engine` `deac11c2` `Add runtime inspector promotion posture`
- `chummer6-ui` `f9d1cf61` `Surface runtime inspector promotion posture`
- `chummer-core-engine` `da9ce4d8` `Add rule environment diff contract`
- `chummer.run-services` `ed2bdea8` `Project rules navigator before-after diffs`
- `chummer6-ui` `089378b2` `Render rules navigator before-after diffs`
- `chummer6-ui` `de36d037` `Add Build Lab handoff receipts to desktop home`
- `chummer6-mobile` `26008a7` `Refresh design mirror pulse`
- `chummer-core-engine` `ee5f2453` `Refresh design mirror pulse`
- `chummer6-media-factory` `cfe8f3a` `Refresh design mirror pulse`
- `chummer-hub-registry` `6f61775` `Refresh design mirror pulse`
- `chummer.run-services` `c3feddbc` `Extend organizer invite rail follow-through`
- `chummer6-design` `678aeb3` `Refresh canonical public guide assets`
- `Chummer6` `af6a4e7` `Sync public guide from design`
- `chummer5a` `fe05f27ab` `Add promotion posture to hub install previews`
- `chummer5a` `b913b85e4` `Implement buildkit hub install previews`
- `chummer5a` `9275d4b6a` `Seed integrated buildkit catalog`
- `chummer5a` `cf01aceb7` `Deepen integrated hub compatibility receipts`
- `chummer5a` `b2566ade6` `Seed integrated NPC vault catalog`
- `chummer-core-engine` `9a92fa3a` `Add NPC compatibility matrices`
- `chummer-core-engine` `bac719f3` `Add NPC hub install previews`
- `chummer5a` `01e4222be` `Add integrated NPC compatibility matrices`
- `chummer5a` `41356c186` `Add integrated NPC hub install previews`
- `chummer.run-services` `f9a80179` `Broaden GM ops governed packet proof`

Media-factory is currently clean again after the latest slice. The new creator-publication proof now carries:

- `handoff.HandoffId` and `handoff.ExplainEntryId` into packet references
- `Next safe action`, `Campaign return`, and `Support closure` evidence lines into publication planning
- publication-projected `NextSafeAction`, `CampaignReturnSummary`, `SupportClosureSummary`, and watchouts even when the explicit handoff record is unavailable
- executable verification in `Chummer.Media.Factory.Runtime.Verify/Program.cs`

Mobile is currently clean again after the latest slice. The new `M12` regression depth now carries:

- explicit workspace-lite regression proof for observer-lane next-safe-action, read-mostly attention posture, and follow-through labels
- explicit workspace-lite regression proof for GM-runboard next-safe-action, quick actions, and continuity-clear attention posture
- projection-backed decision, update, support, restore, and role follow-through anchor text in the play shell instead of generic CTA copy
- cache-pressure decision notices that now reuse the live support next-safe action instead of a generic support-follow-through fallback
- executable `VerifyIndexShellBindsContextualActionLabelsAsync` coverage plus refreshed source-backed local release proof for those labels
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
- explicit progression-path constraint coverage via `MatchedConstraintTags`, `MissingConstraintTags`, and `ConstraintCoverageScore`
- keyed tradeoff summaries plus structured early-consistency and late-ceiling parameters on planned progression paths so downstream consumers can narrate why a path fits or misses campaign constraints
- refreshed `Chummer.CoreEngine.Tests` coverage that locks covered-role, duplicate-role, and deterministic diagnostic ordering in place
- a shared `RulesetEnvironmentDiffProjection` owner contract in `Chummer.Contracts/Rulesets/RulesetExplainContracts.cs` for milestone-8 before/after rule-environment truth
- a shared `RuntimeInspectorPromotionProjection` owner contract plus producer logic so runtime-inspector flows can now expose publication status, channel, rollback posture, and lineage without UI-local schema invention

Run-services now has the new rules-diff slice on top of the earlier hosted/community work. Its current pushed `HEAD` is `052093ce` (`Use contextual build-path labels on hosted links`). The latest committed continuity/projection work now carries:

- shared `NextSafeAction`, `CampaignReturnSummary`, and `SupportClosureSummary` on `CreatorPublicationProjection`
- campaign-spine projection logic that reuses lead build-handoff continuity instead of dropping it
- account and signed-in home surfaces that render creator-publication next-step, return, and support truth directly from the shared projection
- shared `BuildHandoffId` on creator-publication follow-through plus an account detail link back to the related build path
- title-specific build-path deep links on both the signed-in account publication detail and the signed-out public landing build-path card instead of a generic build-follow-through label
- multi-campaign `SeasonBoardEntries` on `CommunityOperatorProjection`, derived directly from shared campaign workspace state
- signed-in home, account work, and live-audit surfaces that bind the new season-board projection instead of inventing a second organizer rail
- calmer workspace ordering that prefers the freshest and widest governed continuity instead of falling back to narrower stale receipts
- organizer invite/sponsorship state on the same community-operator rail, including inviteable campaign choices, recent join codes, recent boost codes, and friendlier stale-code recovery problem details
- signed-in home, account, smoke, and live-audit follow-through for the invite rail so organizer guidance, sponsorship entry, and code recovery stay on one governed surface
- downstream smoke and backup/restore verification that lock registry shelf posture, latest publication posture, operator season-board continuity, and the new organizer invite rail in place
- rules navigator entries that now project explicit before/after diff rows instead of only one coarse summary pair
- account, public landing, and support-assistant surfaces that all reuse the same projected diff truth
- a direct `Chummer.Engine.Contracts` reference on `Chummer.Run.Api` because the hosted layer now consumes the shared diff type in API-local method signatures

UI is now clean again after the latest Build/Explain plus rules-diff slice. The new desktop and workspace depth now carries:

- first-class `BuildLabTeamCoverageProjection` consumption through the shared presentation contract projector
- explicit covered-role, missing-role, duplicate-role, role-pressure, and explain-entry output on both the Blazor and Avalonia Build Lab rails
- per-checkpoint timeline milestone badges, risk badges, and step-level explain ids on the shared `BuildLabPanel`, so the front-door Build Lab sample stops dropping planner risk posture already present in the contract surface
- seeded sample data and renderer coverage that make team optimizer truth visible in both the shell section view and the standalone Build Lab panel
- additional desktop home Build/Explain receipts that surface the lead Build Lab tradeoff and progression outcome alongside the existing handoff/runtime/return/support receipts
- a `RulesNavigatorPanel` that renders concrete before/after diff rows with reasons and explain ids instead of only two plain summary lines
- desktop home campaign/build projectors that now surface the lead rules diff directly in readiness and compatibility receipts
- runtime inspector diagnostics that now surface publication state, update channel, rollback posture, and lineage directly from the shared core projection
- desktop home work-portal buttons now derive concise `Next:` CTA labels from live campaign/build next-safe-action text instead of a generic `Open work follow-through` button
- the build/explain home rail now routes claimed installs without a pinned workspace into the work portal before downloads, which matches the projector's real next-safe-action guidance

The integrated `chummer5a` repo is now carrying the same governed-promotion seam on its still-active all-in-one stack. The new pushed slice now carries:

- shared `RuntimeInspectorPromotionProjection` on runtime inspector, rule-profile preview, and hub install-preview contracts
- one `RuntimeInspectorPromotionNarrator` owner so runtime inspector and rule-profile preview reuse identical promotion, rollback, and lineage language
- runtime-inspector service projections that now emit promotion posture instead of leaving the integrated repo behind the split repos
- hub install-preview receipts and the `Chummer.Hub.Web` install-preview surface that now render publication state, channel, rollback, and lineage for rule profiles
- desktop runtime-inspector dialog fields that now expose promotion and rollback posture in the integrated shell
- a new `scripts/test-runtime-governance.sh` gate covering the touched runtime, preview, hub-web, dialog, and compliance slices
- repo-green compliance refresh for the newer publish-download script wording (`public desktop artifact(s)`)
- BuildKit compatibility/handoff owner contracts and builders that convert the integrated repo’s old `hub_buildkit_apply_preview_not_implemented` defer stub into a real workbench preview
- hub install-preview receipts that now carry `RuntimeCompatibilitySummary`, `CampaignReturnSummary`, and `SupportClosureSummary` for BuildKit handoff truth
- integrated hub-web rendering and Bunit coverage for the new BuildKit handoff summaries so runtime/return/support evidence is visible in the portal head
- BuildKit preview ruleset-mismatch deferral that now tells the user to choose a compatible runtime lane before handoff instead of returning a generic unimplemented stub
- the default integrated BuildKit registry is no longer empty; it now exposes curated SR5 and SR6 starter paths (`street-sam-starter`, `matrix-operator`, `edge-runner-starter`, `shadow-face-starter`, `arcane-scout-starter`) with grounded runtime requirements, prompts, and staged actions
- API integration proof now locks both the catalog endpoints and the hub install-preview endpoint against those real BuildKit entries instead of only proving the unknown-buildkit negative case
- the integrated hub compatibility matrix now carries plain-text `Campaign Return` and `Support Closure` rows for rule profiles, BuildKits, and runtime locks instead of stopping at rules/runtime/install-state rows
- BuildKit compatibility rows now reuse the same narrated runtime, session-handoff, next-safe-action, campaign-return, and support-closure truth already used by the hub install-preview seam
- rule-profile compatibility rows now consume runtime-inspector compatibility diagnostics so rebind-required runtimes push the matrix into explicit review posture instead of looking session-ready by omission
- the runtime-governance helper script now includes both `BuildKitRegistryServiceTests` and `HubProjectCompatibilityServiceTests` so future integrated repo sweeps keep the new seeded catalog and compatibility receipt depth under the same repo-local gate
- the integrated `chummer5a` default NPC vault registry is no longer empty; it now exposes curated SR5 and SR6 NPC entries, NPC packs, and encounter packs (`red-samurai`, `renraku-spider`, `renraku-security`, `renraku-checkpoint`, `neon-razor-biker`, `hex-lantern-mage`, `ancients-hit-squad`, `ancients-smash-and-grab`)
- API search and detail proof now locks the integrated hub against positive-path NPC vault results instead of only buildkits/rule profiles, including mixed catalog search coverage and a direct `npc-entry/red-samurai` detail projection
- the runtime-governance helper script now also includes `NpcVaultRegistryServiceTests`, keeping the seeded integrated NPC vault catalog under the same repo-local gate as BuildKit preview and compatibility proof
- the canonical `chummer-core-engine` hub compatibility surface now also resolves governed matrices for `npc-entry`, `npc-pack`, and `encounter-pack`, including session-runtime posture plus campaign-return/support-closure narratives for milestone-4 prep packets
- the integrated `chummer5a` hub compatibility surface now mirrors that same NPC packet matrix coverage, with positive API proof for `npc-entry/red-samurai/compatibility`
- both the canonical engine and the integrated repo now treat governed NPC entries, NPC packs, and encounter packs as bind-previewable hub projects: `/api/hub/projects/{kind}/{itemId}/install-preview` returns positive-path receipts, return/support summaries, and runtime posture for seeded packet imports
- run-services GM-ops verification and smoke proof now cover governed `npc-pack` imports alongside `encounter-pack`, keeping hosted prep-library/search/export evidence aligned with the widened hub packet support

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
- `chummer5a`: `bash scripts/test-runtime-governance.sh`, `git diff --check`
- `chummer5a` targeted API proof with a local host: `CHUMMER_AMENDS_PATH=/docker/chummer5a/Docker/Amends dotnet /docker/chummer5a/Chummer.Api/bin/Release/net10.0/Chummer.Api.dll --urls http://127.0.0.1:18080` plus `CHUMMER_API_BASE_URL=http://127.0.0.1:18080 dotnet test Chummer.Tests/Chummer.Tests.csproj -c Release -f net10.0 -p:TargetFramework=net10.0 --filter "FullyQualifiedName~ApiIntegrationTests&(Name~Hub_search_endpoint_returns_mixed_catalog_items_for_rulepacks_profiles_and_runtime_locks|Name~Hub_project_detail_endpoint_returns_registered_npc_entry_projection|Name~Hub_project_compatibility_endpoint_returns_registered_npc_entry_matrix|Name~Hub_project_install_preview_endpoint_returns_registered_npc_entry_preview|Name~Hub_project_install_preview_endpoint_returns_registered_buildkit_preview|Name~Buildkits_endpoint_reports_registry_entries_for_registered_rulesets|Name~Buildkits_endpoint_reports_multiple_preview_starters_for_sr6)"`
- `chummer-core-engine`: `bash scripts/ai/verify.sh`, `git diff --check`
- `chummer.run-services`: `bash scripts/ai/run_services_verification.sh`, `bash scripts/ai/run_services_smoke.sh`, `git diff --check`

## Concurrent local changes to respect

These were present in the workspace and were intentionally left alone:

- `/docker/fleet`: dirty `scripts/codexea_route.py` and `tests/test_codexea_route.py` on `main`
- `/docker/EA`: dirty provider/browseract/public-guide-related files on `main`
- `/docker/chummer5a`: dirty `Docker/Downloads/*` release-manifest and artifact files on `Docker`
- `/docker/chummercomplete/chummer.run-services`: dirty concurrent edits in `Chummer.Run.Api/Controllers/PublicLandingController.cs`, `Chummer.Run.Api/Services/PublicTrustPulseService.cs`, and `scripts/hub-live-audit.py`; the staged campaign-memory slice was intentionally kept separate and should stay isolated from those files unless a later slice makes that merge necessary and clearly safe

Do not revert those edits unless a future slice proves they are directly blocking and safe to reconcile.

## What is safe to assume

- The recent Build Lab / campaign OS continuity slices in UI, mobile, core, and media-factory are already landed and pushed.
- The design mirror/public-guide wave is also landed and pushed: canonical design assets and bundle logic changed in `chummer6-design`, the public `Chummer6` repo was re-synced from that bundle, and the repo-local design mirrors in UI/mobile/core/hub-registry/media-factory were refreshed to match.
- The media-factory creator-publication planner now preserves continuity from either the explicit Build Lab handoff or the richer creator-publication projection itself, with verification coverage for both paths.
- Run-services now preserves that creator-publication continuity on the signed-in API and MVC surfaces instead of reducing publication status to trust/discovery/status only, and it keeps a direct link back to the related build path.
- Run-services campaign workspace, workspace digest, and workspace server-plane projections now also carry a first-class `CampaignMemoryProjection`, and `/home/work` plus `/account/work/workspaces/{workspaceId}` render that bounded memory summary, return cue, next step, and evidence directly from shared hosted projection truth.
- Run-services community-operator projections now expose a first-class multi-campaign season board, and the signed-in home/account/audit surfaces bind it directly from the shared campaign spine.
- Run-services operator season-board entries now also carry campaign-memory summary and return truth, and both `/account/work` and `/home/work` render that long-lived continuity directly on the operator rail instead of only inside per-workspace drawers.
- Run-services operator season-board entries now also carry one lead governed consequence summary, and both `/account/work` and `/home/work` render that consequence follow-through directly from the shared operator projection.
- Run-services operator season-board entries now also carry one lead recap summary, and both `/account/work` and `/home/work` render that recap follow-through directly from the shared operator projection.
- Run-services organizer flows now keep invite and sponsorship issuance, stale-code recovery copy, and public/signed-in follow-through on the same governed operator rail instead of splitting them across generic errors and ad hoc guidance.
- The shared rule-environment before/after seam now exists: core owns the diff contract, Hub projects diff rows onto rules navigator answers, desktop home consumes the lead diff, and support/public surfaces reuse the same text.
- Runtime-inspector promotion posture now also has a shared seam: core owns the promotion/rollback payload and desktop runtime diagnostics consume it directly instead of inventing UI-local publication or rollback language.
- The integrated `chummer5a` stack now also has governed-promotion posture threaded through runtime inspector, rule-profile preview, hub install preview, and the desktop runtime dialog; future integrated-repo work should build on that seam instead of reinvesting in ad hoc publication strings.
- The integrated `chummer5a` hub stack no longer defers BuildKit install preview as “not implemented”; it now emits real workbench/runtime/return/support receipts and ruleset-mismatch guidance through the same hub preview seam.
- The integrated `chummer5a` default BuildKit catalog now has real seeded SR5/SR6 starter entries, so future integrated repo work can assume positive-path BuildKit catalog and hub-preview coverage exists instead of an empty registry stub.
- The integrated `chummer5a` hub compatibility surface now exposes campaign-return and support-closure posture for rule profiles, BuildKits, and runtime locks, with runtime-inspector-driven review posture for profile rebind drift.
- The integrated `chummer5a` default NPC vault registry now has real seeded SR5/SR6 entries, packs, and encounter packets, so future integrated repo work can assume positive-path NPC catalog search and detail coverage exists instead of an empty registry stub.
- The canonical `chummer-core-engine` and integrated `chummer5a` hub compatibility surfaces now both expose governed matrices for `npc-entry`, `npc-pack`, and `encounter-pack`.
- The canonical `chummer-core-engine` and integrated `chummer5a` hub install-preview surfaces now both expose positive-path bind-preview receipts for seeded NPC packets, including campaign-return and support-closure summaries.
- Hosted GM-ops proof now covers both `encounter-pack` and `npc-pack` governed imports in verification and smoke, so milestone-4 roster/packet continuity has stronger end-to-end evidence in `chummer.run-services`.
- UI Build Lab surfaces now consume explicit team-coverage contract data and surface covered, missing, duplicate, and role-pressure truth instead of inferring optimizer posture from overlap badges alone.
- UI desktop home action rows now consume live next-safe-action projection text for campaign/build/workspace follow-through buttons instead of generic work-portal CTA copy.
- UI desktop home now consumes hosted server-plane campaign memory and travel-mode continuity directly on the campaign return panel instead of dropping those hosted cues at the client boundary.
- Desktop home Build/Explain now includes the lead Build Lab tradeoff and progression receipt in the same compatibility-receipt lane as runtime, rules, migration, and publication evidence.
- Hub-registry publication read models now expose explicit moderation next steps, explicit trust/discovery/lineage posture, explicit artifact shelf posture, and the latest publication state/trust band directly on artifact detail projections.
- Mobile workspace-lite coverage now includes observer and GM role-depth assertions, not just player-lane continuity proof.
- Mobile workspace-lite now exposes a first-class campaign-memory summary and memory-return cue beside recap, travel, and offline-prefetch posture, keeping the same governed memory lane visible for player, observer, and GM shells.
- Mobile workspace-lite and restore links now render projection-backed action text for decision/update/support/restore/role follow-through instead of generic anchor copy.
- Core Build Lab team coverage now exposes which required roles are already covered and which role tags are duplicated, with deterministic duplicate-role diagnostics and explain parameters.
- Core Build Lab progression planning now exposes explicit matched/missing campaign constraints, deterministic constraint-coverage scoring, and keyed tradeoff summaries instead of only one coarse constraint-count parameter plus a gap diagnostic.
- The shared UI Build Lab panel now renders the timeline milestone/risk badges and step-level explain ids that already exist on the progression contract surface, so the home/sample rail no longer hides planner risk posture.
- Core compatibility matrices now carry the BuildKit next-safe-action inside the session-runtime handoff notes, and UI has regression proof that the HTTP compatibility fallback preserves that text into desktop build previews.
- Hub-registry canonical release-channel materialization now preserves embedded `releaseProof` when regenerating from an existing manifest and emits explicit non-null artifact/runtime compatibility state instead of leaving release truth partially null.
- The year-end milestone set is still materially unfinished across the broader program; there is no honest basis to treat the design as complete.
- The next session should start from live repo evidence, not from a stale assumption that the just-landed slices are still pending.

## Next useful slices

Only start one after rechecking the live repo state:

1. Re-derive the next executable open milestone from `chummer6-design` instead of assuming the previous dirty slices are still pending; hosted, desktop, and mobile continuity have all moved again in this pass.
2. Highest-leverage candidates from current repo evidence are the next W1/W3 follow-through after the new campaign-memory baseline: broader hosted consequence/recap synthesis, additional operator/community depth on the same account/control backbone, or publication/exchange continuity beyond the creator-publication, shelf, and operator-memory posture already landed.
3. Another clean W2 slice is available immediately in UI/mobile/front-door surfaces: consume the newer Build Lab planner receipt depth more broadly instead of leaving constraint-coverage and tradeoff posture trapped in owner-side tests or one sample panel.
4. Refresh fleet handoff and mirror artifacts again after the next canonical-design or cross-repo milestone slice so a future session does not reopen already-shipped work.

## Resume posture

Start with repo status plus targeted verification, then select the highest-impact clean slice. Do not resume quartermaster/controller work unless fresh evidence makes it the top gap again.
