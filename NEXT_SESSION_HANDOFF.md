# Next Session Handoff

Date: 2026-03-29
Workspace focus: `/docker/fleet`, `/docker/chummer5a`, plus the active Chummer6 repos in `/docker/chummercomplete` and `/docker/fleet/repos`

## Current state

The latest autonomous wave pushed additive Build/Explain depth, organizer guidance, campaign-publication proof, and a canonical public-guide refresh across multiple repos. The work already landed should be treated as baseline, not as an unfinished branch to reopen blindly.

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
- a shared `RulesetEnvironmentDiffProjection` owner contract in `Chummer.Contracts/Rulesets/RulesetExplainContracts.cs` for milestone-8 before/after rule-environment truth
- a shared `RuntimeInspectorPromotionProjection` owner contract plus producer logic so runtime-inspector flows can now expose publication status, channel, rollback posture, and lineage without UI-local schema invention

Run-services now has the new rules-diff slice on top of the earlier hosted/community work. Its current pushed `HEAD` is `ed2bdea8` (`Project rules navigator before-after diffs`). The latest committed continuity/projection work now carries:

- shared `NextSafeAction`, `CampaignReturnSummary`, and `SupportClosureSummary` on `CreatorPublicationProjection`
- campaign-spine projection logic that reuses lead build-handoff continuity instead of dropping it
- account and signed-in home surfaces that render creator-publication next-step, return, and support truth directly from the shared projection
- shared `BuildHandoffId` on creator-publication follow-through plus an account detail link back to the related build path
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
- seeded sample data and renderer coverage that make team optimizer truth visible in both the shell section view and the standalone Build Lab panel
- additional desktop home Build/Explain receipts that surface the lead Build Lab tradeoff and progression outcome alongside the existing handoff/runtime/return/support receipts
- a `RulesNavigatorPanel` that renders concrete before/after diff rows with reasons and explain ids instead of only two plain summary lines
- desktop home campaign/build projectors that now surface the lead rules diff directly in readiness and compatibility receipts
- runtime inspector diagnostics that now surface publication state, update channel, rollback posture, and lineage directly from the shared core projection

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
- `chummer5a` targeted API proof with a local host: `CHUMMER_AMENDS_PATH=/docker/chummer5a/Docker/Amends dotnet /docker/chummer5a/Chummer.Api/bin/Release/net10.0/Chummer.Api.dll --urls http://127.0.0.1:18080` plus `CHUMMER_API_BASE_URL=http://127.0.0.1:18080 dotnet test Chummer.Tests/Chummer.Tests.csproj -c Release -f net10.0 -p:TargetFramework=net10.0 --filter "FullyQualifiedName~ApiIntegrationTests&(Name~Buildkits_endpoint_reports_registry_entries_for_registered_rulesets|Name~Buildkits_endpoint_reports_multiple_preview_starters_for_sr6|Name~Hub_project_install_preview_endpoint_returns_registered_buildkit_preview)"`

## Concurrent local changes to respect

These were present in the workspace and were intentionally left alone:

- `/docker/EA`: dirty provider/browseract/public-guide-related files on `main`
- `/docker/chummer5a`: dirty `Docker/Downloads/*` release-manifest and artifact files on `Docker`

Do not revert those edits unless a future slice proves they are directly blocking and safe to reconcile.

## What is safe to assume

- The recent Build Lab / campaign OS continuity slices in UI, mobile, core, and media-factory are already landed and pushed.
- The design mirror/public-guide wave is also landed and pushed: canonical design assets and bundle logic changed in `chummer6-design`, the public `Chummer6` repo was re-synced from that bundle, and the repo-local design mirrors in UI/mobile/core/hub-registry/media-factory were refreshed to match.
- The media-factory creator-publication planner now preserves continuity from either the explicit Build Lab handoff or the richer creator-publication projection itself, with verification coverage for both paths.
- Run-services now preserves that creator-publication continuity on the signed-in API and MVC surfaces instead of reducing publication status to trust/discovery/status only, and it keeps a direct link back to the related build path.
- Run-services community-operator projections now expose a first-class multi-campaign season board, and the signed-in home/account/audit surfaces bind it directly from the shared campaign spine.
- Run-services organizer flows now keep invite and sponsorship issuance, stale-code recovery copy, and public/signed-in follow-through on the same governed operator rail instead of splitting them across generic errors and ad hoc guidance.
- The shared rule-environment before/after seam now exists: core owns the diff contract, Hub projects diff rows onto rules navigator answers, desktop home consumes the lead diff, and support/public surfaces reuse the same text.
- Runtime-inspector promotion posture now also has a shared seam: core owns the promotion/rollback payload and desktop runtime diagnostics consume it directly instead of inventing UI-local publication or rollback language.
- The integrated `chummer5a` stack now also has governed-promotion posture threaded through runtime inspector, rule-profile preview, hub install preview, and the desktop runtime dialog; future integrated-repo work should build on that seam instead of reinvesting in ad hoc publication strings.
- The integrated `chummer5a` hub stack no longer defers BuildKit install preview as “not implemented”; it now emits real workbench/runtime/return/support receipts and ruleset-mismatch guidance through the same hub preview seam.
- The integrated `chummer5a` default BuildKit catalog now has real seeded SR5/SR6 starter entries, so future integrated repo work can assume positive-path BuildKit catalog and hub-preview coverage exists instead of an empty registry stub.
- The integrated `chummer5a` hub compatibility surface now exposes campaign-return and support-closure posture for rule profiles, BuildKits, and runtime locks, with runtime-inspector-driven review posture for profile rebind drift.
- UI Build Lab surfaces now consume explicit team-coverage contract data and surface covered, missing, duplicate, and role-pressure truth instead of inferring optimizer posture from overlap badges alone.
- Desktop home Build/Explain now includes the lead Build Lab tradeoff and progression receipt in the same compatibility-receipt lane as runtime, rules, migration, and publication evidence.
- Hub-registry publication read models now expose explicit moderation next steps, explicit trust/discovery/lineage posture, explicit artifact shelf posture, and the latest publication state/trust band directly on artifact detail projections.
- Mobile workspace-lite coverage now includes observer and GM role-depth assertions, not just player-lane continuity proof.
- Core Build Lab team coverage now exposes which required roles are already covered and which role tags are duplicated, with deterministic duplicate-role diagnostics and explain parameters.
- Core compatibility matrices now carry the BuildKit next-safe-action inside the session-runtime handoff notes, and UI has regression proof that the HTTP compatibility fallback preserves that text into desktop build previews.
- Hub-registry canonical release-channel materialization now preserves embedded `releaseProof` when regenerating from an existing manifest and emits explicit non-null artifact/runtime compatibility state instead of leaving release truth partially null.
- The year-end milestone set is still materially unfinished across the broader program; there is no honest basis to treat the design as complete.
- The next session should start from live repo evidence, not from a stale assumption that the just-landed slices are still pending.

## Next useful slices

Only start one after rechecking the live repo state:

1. Re-derive the next executable open milestone from `chummer6-design` instead of assuming the previous dirty slices are still pending; the active repos are clean again.
2. Highest-leverage candidates from current repo evidence are now the next W2/W3 follow-through after the rules-diff slice: broader governed-promotion/apply depth, BuildKit receipt/application follow-through beyond preview, explain receipts that reuse the new promotion posture, or publication/exchange continuity beyond the slices already landed.
3. Refresh fleet handoff and mirror artifacts again after the next canonical-design or cross-repo milestone slice so a future session does not reopen already-shipped work.

## Resume posture

Start with repo status plus targeted verification, then select the highest-impact clean slice. Do not resume quartermaster/controller work unless fresh evidence makes it the top gap again.
