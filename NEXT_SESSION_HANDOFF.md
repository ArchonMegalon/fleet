# Next Session Handoff

Date: 2026-03-30
Workspace focus: `/docker/fleet`, `/docker/EA`, `/docker/chummercomplete/*`, `/docker/fleet/repos/*`, `/docker/chummer5a`

## Handoff refresh (2026-03-30 latest cross-repo sync)

- 2026-03-30: `chummer6-core` Build Lab hyphenated-role coverage and watchout ordering are now fixed and verifier-guarded.
  - `DefaultBuildLabService`, compatibility `BuildLabEngine`, and `BuildLabWorkspaceProjectionFactory` now preserve hyphenated role tags such as `street-samurai` and `matrix-specialist` when they derive progression paths, team coverage, campaign-fit summaries, and overlap labels, instead of truncating the tag to its last token and zeroing covered-role output.
  - `BuildLabWorkspaceProjectionFactory` now prioritizes missing-role and late-checkpoint risk watchouts ahead of lower-priority variant warnings so milestone-7 crew-gap signals stay visible in the first bounded watchout set.
  - `Chummer.CoreEngine.Tests/Program.cs` now hard-fails on deterministic Build route scaffold output plus Build Lab intake campaign-fit, support-closure, and missing-role watchout wording.
  - Verified via `cd /docker/chummercomplete/chummer-core-engine && bash scripts/ai/verify.sh`.

- 2026-03-30: OODA placement rule is now explicit in canon.
  - `chummer-design` now says the product-governor/control OODA semantics live in design canon, the durable executable loop lives in Fleet, Hub owns the user/install/community/support truth those loops read or update, and shell sessions are entrypoints only.
  - Fleet mirror scope now carries that same boundary in `.codex-design/repo/IMPLEMENTATION_SCOPE.md` plus `.codex-design/product/PRODUCT_GOVERNOR_AND_AUTOPILOT_LOOP.md`.

- 2026-03-30: `chummer-design` `19bae79` `Refresh weekly pulse and editorial guide bundle`
  - the weekly pulse generator now emits explicit `closure_health`, `adoption_health`, `progress_trend`, and richer provider-route stewardship signals, and the product invariants now validate those supporting signal objects directly.
  - editorial cover validation/materialization now owns the current public-guide cover set more explicitly, and the public guide plus horizon copy/assets were refreshed to the newer editorial surface.
  - verified via `cd /docker/chummercomplete/chummer-design && bash scripts/ai/verify.sh`.

- 2026-03-30: Chummer Design public-guide verification blocker was fixed by correcting double-escaped literal-question regexes in `scripts/ai/verify.sh` (`FAQ`, `download/auth`, `How Can I Help`, and FAQ registry heading assertions). `bash scripts/ai/verify.sh` now returns `ok` in-place.

- 2026-03-30: Restored `chummer6-core` contract-posture after local regression by reintroducing package-boundary references to `Chummer.Engine.Contracts` (`Version="$(ChummerEngineContractsPackageVersion)"`) in active consumers and removing reverted source-project references. Verified:
  - `cd /docker/chummercomplete/chummer6-core && bash scripts/ai/verify.sh`
  - `cd /docker/chummercomplete/chummer-design && bash scripts/ai/verify.sh`
  - `cd /docker/chummercomplete/chummer-hub-registry && bash scripts/ai/verify.sh`
  - `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_verification.sh && bash scripts/ai/run_services_smoke.sh`
  - `cd /docker/chummercomplete/chummer6-mobile && bash scripts/ai/verify.sh` (rerun)

- 2026-03-30: `chummer6-core` Build Lab workbench entry is now live and actively guarded on the active core verifier path.
  - Current repo state now exposes `build-lab` from workspace parsing/codecs, binds live workspace ids on the returned projection, and surfaces the Create/Build Lab tab-action path through hosted plus SR4/SR5/SR6 shell catalogs and career workflow surfaces.
  - `Chummer.CoreEngine.Tests/Program.cs` now hard-fails on regressions in Build Lab intake projection shaping, workspace-id rebinding, shell/workflow exposure, and SR4/SR6 codec section projection.
  - Verified via `cd /docker/chummercomplete/chummer6-core && bash scripts/ai/build.sh` and `cd /docker/chummercomplete/chummer6-core && bash scripts/ai/test_core_engine.sh`.

- 2026-03-30: `chummer-design` now records Build Lab milestones `6` and `7` as complete in both canonical design and the Fleet mirror.
  - Closeout evidence is already repo-local and green across the owner lanes: `chummer6-core` deterministic planner and team-coverage assertions, `chummer6-ui` Build Lab shell/workbench coverage, `chummer6-hub` build-handoff follow-through plus signed-in surface smoke, and Fleet journey-gate materialization all stayed ready on current evidence.
  - Verified via `cd /docker/chummercomplete/chummer6-core && bash scripts/ai/test_core_engine.sh`, `cd /docker/chummercomplete/chummer6-ui && bash scripts/ai/milestones/b3-build-lab-check.sh`, `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_verification.sh`, `cd /docker/chummercomplete/chummer6-mobile && bash scripts/ai/verify.sh`, and `python3 /docker/fleet/scripts/materialize_journey_gates.py --out /tmp/JOURNEY_GATES.current.json --status-plane /docker/fleet/.codex-studio/published/STATUS_PLANE.generated.yaml --progress-report /docker/fleet/.codex-studio/published/PROGRESS_REPORT.generated.json --progress-history /docker/fleet/.codex-studio/published/PROGRESS_HISTORY.generated.json --support-packets /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json`.

- The active frontier from `chummer-design` is now W1 milestones `3`, `4`, and `5`; W2 milestone work shifts to `8`, `9`, and `10` after the Build Lab planner/team-optimizer closeout.
- Fleet now has a repo-local design-completion supervisor:
  - `scripts/chummer_design_supervisor.py` derives the active frontier directly from the canonical registry, roadmap, and `NEXT_SESSION_HANDOFF.md`, writes durable run state under `state/chummer_design_supervisor/`, and launches bounded `codex exec` worker runs across `/docker/fleet`, `/docker/chummercomplete`, `/docker/fleet/repos`, `/docker/chummer5a`, and `/docker/EA`.
  - `scripts/run_chummer_design_supervisor.sh` is the launch helper and now expands env-driven steering/account flags (`CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_OWNER_IDS`, `CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_ALIASES`, `CHUMMER_DESIGN_SUPERVISOR_FOCUS_OWNER`, `CHUMMER_DESIGN_SUPERVISOR_FOCUS_TEXT`) before it starts the loop.
  - `docker-compose.yml` now includes `fleet-design-supervisor`, so a normal Fleet compose boot owns restart-on-reboot for the loop instead of relying on a shell or tmux session.
  - `python3 scripts/chummer_design_supervisor.py trace --state-root state/chummer_design_supervisor --limit 20` now renders the recent OODA/operator history directly from Fleet state instead of forcing raw JSONL inspection.
  - Retryable worker-model failures now surface a compact failure hint in `status`/`trace`, and the supervisor automatically retries fallback models (`--fallback-worker-model`, default fallback `gpt-5.4`) when the current model returns a quota/support-style error.
  - The supervisor now also rotates across protected operator account pools from `config/accounts.yaml` by default, including `tibor.girschele`, `the.girscheles`, and `archon.megalon`, with source-aware backoff for usage-limit/auth/rate-limit failures.
  - Steering is now a first-class seam: use `--focus-owner chummer6-ui` or `CHUMMER_DESIGN_SUPERVISOR_FOCUS_OWNER=chummer6-ui` to bias the frontier toward finishing the desktop client first without dropping the rest of the open milestone set.
  - The current dry-run derivation now selects milestones `3`, `4`, and `5` as the highest-priority open frontier and leaves milestones `8` through `14` open for later re-derivation.
- This session materially deepened artifact-shelf and creator-publication posture without treating a clean repo as done:
  - `chummer-design` `b1451c2` `Add the public status route to canon`
    - the canonical public landing manifest and navigation now both treat `/status` as a first-class public route instead of leaving milestone-owned status truth implied by policy docs alone.
    - owner-repo verification stayed green via `bash scripts/ai/verify.sh`.
  - `chummer.run-services` / `chummer6-hub` `3aa4979a` `Materialize the public status route`
    - `/status` is now a first-class hosted page instead of redirecting to `/now`, and it reuses the shared public trust pulse plus shared signed-in trust panel while surfacing release posture, current caution, campaign-OS proof, and a direct progress-poster/report lane.
    - the same slice also fixed a live cleanroom blocker in the new AI observation seam by binding observation request/response use sites to the canonical `Chummer.Run.Contracts.Gateway` contracts instead of ambiguous duplicated gateway DTO names.
    - hosted verification is green again via `bash scripts/ai/build_r1_cleanroom.sh`, `bash scripts/ai/run_services_verification.sh`, and `bash scripts/ai/run_services_smoke.sh`.
  - `chummer.run-services` / `chummer6-hub` `8571a999` `Add explicit signed-in artifact shelf views`
    - signed-in `/artifacts` now exposes first-class `all`, `personal`, `campaign`, and `creator` views instead of one blended overlay, and the personal lane now includes dossier-backed governed artifact entries so the same artifact truth can actually be browsed across personal, campaign, and creator rails.
    - hosted verification and smoke stayed green after the filter, shelf merge, dossier-backed personal entry, and source/runtime proof updates.
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
  - `chummer.run-services` / `chummer6-hub` `82de80ab` `Show release proof on landing trust pulse`
    - the public landing trust pulse now renders the explicit release-proof row, so the front door says what is fixed instead of keeping that release-proof truth trapped in the pulse model.
    - hosted verification and smoke stayed green after the public release-proof slice.
  - `chummer.run-services` / `chummer6-hub` `6aa37351` `Show launch readiness on landing trust pulse`
    - the public landing trust pulse now renders launch-readiness posture directly from the weekly pulse instead of leaving that readiness signal on deeper trust pages only.
    - hosted verification and smoke stayed green after the public launch-readiness slice.
  - `chummer.run-services` / `chummer6-hub` `02b3c176` `Show closure health on landing trust pulse`
    - the public landing trust pulse now also renders closure-health posture, so the front door trust view shows access, release proof, launch readiness, adoption, closure, and caution from the same governed pulse.
    - hosted verification and smoke stayed green after the public closure-health slice.
  - `chummer.run-services` / `chummer6-hub` `aa54a641` `Show pulse trend on landing trust pulse`
    - the public landing trust pulse now also renders progress trend and provider-route stewardship, so those W20 signals are no longer model-only on the front door.
    - hosted verification and smoke stayed green after the public pulse-trend slice.
  - `chummer.run-services` / `chummer6-hub` `4746857e` `Show journey pulse on landing trust pulse`
    - the public landing trust pulse now renders the journey pulse row as well, completing the carry-through of all governed weekly pulse rows onto the front-door trust surface.
    - hosted verification and smoke stayed green after the public journey-pulse slice.
  - `chummer.run-services` / `chummer6-hub` `15fc9e0f` `Render shared landing trust pulse rows`
    - the public landing trust pulse is now rendered from the shared row collection and shared trend samples instead of one brittle hand-picked subset, so future weekly-pulse additions stop depending on front-door template drift.
    - hosted verification and smoke stayed green after the shared-row landing cleanup.
  - `chummer.run-services` / `chummer6-hub` `66d6beb1` `Fix participation handoffs and recap shelf contracts`
    - guest and signed-in participate routes now prove the right guided-contribution and beta-follow-through dispatch semantics, while the selected workspace aftermath shelf on home/account now carries creator-publication trust ranking, bounded discoverability, and direct publication follow-through instead of stopping at state-only posture.
    - hosted verification and smoke stayed green after the participate-routing plus recap-shelf contract carry-through.
  - `chummer.run-services` / `chummer6-hub` `6a07d123` `Carry artifact shelf posture into calmer workspace views`
    - the calmer shared workspace recap shelf on account now inherits the same creator-publication trust band, discoverability, ownership, publication summary, next-step, and publication link posture as the richer selected server-plane view instead of collapsing back to label-plus-id.
    - `CampaignSpineService` now enriches workspace recap-shelf projections before they fan out into calmer account views, and hosted verification plus smoke stayed green after the carry-through.
  - `chummer.run-services` / `chummer6-hub` `8502ec1c` `Clarify creator publication provenance and visibility`
    - signed-in home and account publication surfaces now call provenance what it is, show explicit visibility posture beside trust ranking and discovery, and keep the calmer publication list aligned with the richer selected detail card.
    - hosted verification and smoke stayed green after the creator-publication posture clarification slice.
  - `chummer.run-services` / `chummer6-hub` `1dc7a207` `Carry creator publication lineage through hosted surfaces`
    - creator-publication projections now carry explicit lineage summaries, and signed-in home plus account publication surfaces render that lineage posture alongside provenance, visibility, trust ranking, and discovery instead of leaving lineage trapped behind deeper registry truth.
    - hosted verification and smoke stayed green after the contract-plus-view lineage carry-through.
  - `chummer.run-services` / `chummer6-hub` `3479db83` `Show recap lineage on hosted shelves`
    - signed-in home aftermath cards plus account recap-shelf drawers now reuse the linked creator-publication projection to render lineage directly on recap return surfaces instead of forcing a separate publication-detail hop.
    - hosted verification and smoke stayed green after the recap-lineage carry-through slice.
  - `chummer.run-services` / `chummer6-hub` `6ee34dc7` `Prove registry shelf audience filters downstream`
    - downstream hosted smoke now proves creator, campaign, personal, and invalid shelf-audience filter behavior against the shared registry controller, so artifact-shelf-v2 audience views are guarded at the consumer boundary too.
    - hosted verification and smoke stayed green after the downstream artifact-shelf-v2 proof slice.
  - `chummer-hub-registry` `5d085cd` `Expose full publication trust posture`
    - registry search, preview, and projection contracts now carry publication trust summary, discovery summary, lineage summary, and discoverability posture in addition to trust band and next-safe action, and both owner verify plus downstream hosted smoke stayed green.
  - `chummer-hub-registry` `95917ed` `Filter artifact shelves by audience`
    - registry search and projection-list endpoints now support explicit `shelfAudience` filters for personal, creator, campaign, owner-only, and retained-history views instead of forcing client-side ad hoc filtering.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer-media-factory` `404c5af` `Anchor creator publication packets to governed status`
    - creator-publication plans now keep the publication id as a first-class packet reference and attachment target.
    - packet evidence is now explicitly labeled for provenance, discovery, ownership, and publication state instead of leaving those semantics implicit.
  - `chummer-media-factory` `ad59123` `Label creator publication trust posture`
    - creator-publication packet evidence now labels trust band and discoverability alongside provenance, discovery, ownership, and state, so downstream publication packets preserve trust posture instead of flattening it away.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer-media-factory` `bd372d6` `Carry creator publication lineage into media packets`
    - creator-publication packet evidence now preserves lineage alongside provenance, trust, discovery, discoverability, ownership, and state, so packet consumers can keep governed successor posture without reopening the hosted publication card.
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
  - `chummer6-mobile` `136a359` `Carry artifact trust into mobile follow-through`
    - workspace-lite follow-through labels now carry artifact publication trust posture and the creator-publication next step, so mobile no longer confines recap trust to one summary paragraph.
    - mobile verification stayed green after the follow-through expansion.
  - `chummer6-mobile` `f38c8bb` `Expose recap lineage in mobile workspace lite`
    - workspace-lite recap surfaces now expose a dedicated lineage summary and carry that lineage into follow-through labels, so mobile keeps creator-publication continuity visible without leaving it buried inside hosted publication status only.
    - mobile verification stayed green after the projector, shell, and regression updates.
  - `chummer6-mobile` `c7afeda` `Add mobile artifact shelf browse views`
    - workspace-lite now emits explicit personal, campaign, and published artifact-shelf browse targets with role-aware defaults, and the mobile play shell renders those first-class links instead of leaving milestone `15` at prose-only audience summaries on the recap lane.
    - mobile verification stayed green after the projector, shell, and regression updates.
  - `chummer6-ui` `c139072f` `Materialize desktop support and recovery surfaces`
    - desktop now ships first-class update, support, support-case, devices/access, report-issue, and crash-recovery windows with persistent shell navigation, preference-backed return state, installer/runtime follow-through, and deeper localization/accessibility proof instead of leaving W4 desktop parity trapped in home-card shortcuts only.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer6-ui` `f55a733e` `Carry first-session proof into desktop home`
    - the native desktop home now surfaces legal-runner, understandable-return, campaign-ready, starter-next, and first-session evidence lines from the grounded hosted campaign contracts instead of leaving milestone `19` embodied only on hosted and mobile surfaces.
    - desktop home fallback logic now reuses first-session next-step truth when a broader workspace next safe action is not yet enough, and owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer6-ui` `6ffaba0a` `Surface artifact trust on desktop home`
    - the native desktop home now keeps recap-shelf trust ranking and discoverability visible alongside audience, ownership, publication state, and next-step posture instead of flattening W15/W18 artifact truth down to publication state alone.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer6-ui` `e7ab6316` `Deepen desktop publication continuity`
    - the native desktop home now keeps creator-publication visibility, lineage, and next-step posture visible alongside provenance instead of flattening creator-publication truth down to one trust line after hosted/mobile already carried the richer continuity.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer6-ui` `6ffc0893` `Add desktop artifact shelf browse actions`
    - the native desktop home now exposes direct `My stuff`, `Campaign stuff`, and `Published stuff` actions that open the governed signed-in artifact shelf views, and campaign readiness highlights explicitly call out that the same artifact truth stays browseable from one shelf instead of collapsing milestone `15` back to prose-only parity on desktop.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `chummer-design` `b30ba93` `Refresh editorial public guide bundle assets`
    - canonical public-guide markdown, export manifest, editorial-cover registry, source plates, and bundle generators are now refreshed together instead of leaving the new curated image-canon wave stranded in design-only dirt.
    - owner-repo verification is green via `bash scripts/ai/verify.sh`.
  - `Chummer6` `e2c5928` `Sync editorial public guide bundle`
    - the public guide consumer repo now mirrors the refreshed canonical markdown, curated assets, and bundle outputs from `chummer-design` instead of drifting behind the editorial-cover refresh.
    - downstream verification is green via `bash scripts/verify_public_guide.sh`.
  - `chummer.run-services` / `chummer6-hub` `4827b55d` `Refresh design mirrors after public guide sync`
    - the hosted repo mirror now picks up the refreshed public-guide export manifest and weekly product pulse after the editorial-canon publish, so downstream guided surfaces are aligned with the latest design bundle.
  - `chummer.run-services` / `chummer6-hub` `dce909e8` `Project account trust status on hosted surfaces`
    - signed-in account routes now reuse the shared install-specific trust panel instead of stopping at a link-only guidance rail, and the shared panel now carries explicit `Who can get it now` posture alongside recommendation, adoption health, release proof, fix availability, and current caution.
    - hosted public and account routes now stay on one shared signed-in trust projection contract, while owner verification and in-process smoke both stayed green after the extraction.
  - `chummer.run-services` / `chummer6-hub` `23ebab5f` `Reuse signed-in trust snapshot on operator rail`
    - the account work member-guidance rail now reuses the same signed-in trust snapshot for current access posture, promoted install path, release proof, and caution instead of making organizers translate those states from separate trust or downloads pages.
    - hosted verification and in-process smoke both stayed green after the operator guidance carry-through.
  - `chummer.run-services` / `chummer6-hub` `502f7774` `Reuse signed-in trust posture on home`
    - signed-in home now reuses the shared trust panel itself and threads who-can-get-it-now, fix availability, and current caution directly into the lead operator card instead of leaving that posture trapped on account, downloads, help, and now only.
    - hosted verification and in-process smoke both stayed green after the home trust carry-through.
  - `chummer.run-services` / `chummer6-hub` `bd9eb5f7` `Show trust status across signed-in home sections`
    - the shared signed-in trust panel now stays visible on home overview, access, and work sections instead of disappearing once the user leaves the overview tab.
    - hosted verification and in-process smoke both stayed green after the section-wide trust visibility follow-through.
  - `chummer.run-services` / `chummer6-hub` `69a87481` `Project signed-in trust status on contact`
    - the contact/support-intake trust page now projects the same signed-in trust status used on downloads, help, now, account, and home, so install-specific access posture is visible before a signed-in user opens or expands a case.
    - hosted verification and in-process smoke both stayed green after the contact trust carry-through.
  - `chummer.run-services` / `chummer6-hub` `ed2d08f5` `Deepen support confirmation trust carry-through`
    - the post-intake support confirmation route now keeps the shared signed-in trust panel, linked-install readiness, fix-confirmation guidance, and release-lane summary attached to the submitted case instead of collapsing back to case-id prose after contact submission.
    - hosted verification and in-process smoke both stayed green after the support-confirmation trust carry-through.
  - `chummer.run-services` / `chummer6-hub` `0b7c9001` `Deepen front-door trust and download language`
    - the public landing front door now reuses the shared signed-in trust panel for authenticated users, while downloads/now/help copy and release-selection summaries switch from brittle installer-first wording to the current public-download language without losing the grounded shelf/trust truth.
    - hosted verification and in-process smoke both stayed green after the front-door trust and download-language carry-through, including the necessary concurrent public-copy changes already present in the repo.
  - `chummer.run-services` / `chummer6-hub` `a7830a76` `Carry trust posture onto FAQ`
    - the FAQ route now carries the same weekly trust pulse and shared signed-in install-trust panel used on the other public trust/help routes, so authenticated and guest readers no longer lose current release posture when they pivot into FAQ answers.
    - hosted verification and in-process smoke both stayed green after the FAQ trust carry-through.
  - `chummer.run-services` / `chummer6-hub` `07285f75` `Carry weekly pulse onto support confirmation`
    - the post-intake support confirmation route now carries the shared weekly public trust pulse as well as the signed-in trust snapshot, so release posture stays visible immediately after support intake instead of dropping back to case-only context.
    - hosted verification and in-process smoke both stayed green after the support-confirmation pulse carry-through.
  - `chummer.run-services` / `chummer6-hub` `818d75c8` `Carry trust posture across public routes`
    - product story, participate, horizons, and artifacts now carry the same shared weekly public trust pulse and signed-in install-trust panel used on the other public routes, so authenticated and guest readers no longer lose current release posture when they move beyond landing/help/downloads.
    - hosted verification and in-process smoke both stayed green after the wider public-route trust carry-through.
  - `chummer.run-services` / `chummer6-hub` `b9762b38` `Carry trust posture onto feature details`
    - roadmap and artifact detail pages now carry the shared weekly public trust pulse and signed-in install-trust panel too, so the deeper detail routes no longer drop release posture when users drill into proof or horizon specifics.
    - hosted verification and in-process smoke both stayed green after the feature-detail trust carry-through.
  - `chummer.run-services` / `chummer6-hub` `89bd4bcb` `Carry trust posture onto download handoff`
    - the signed-in download handoff route now carries the shared weekly public trust pulse and signed-in install-trust panel too, so the account-aware download path no longer drops current release posture at the moment the user leaves downloads for the final linked handoff.
    - hosted verification and in-process smoke both stayed green after the download-handoff trust carry-through.
  - `chummer.run-services` / `chummer6-hub` `be659a46` `Carry signed-in trust posture onto privacy and terms`
    - privacy and terms now project the same shared signed-in install-trust panel used across the rest of the trust/help/download chain, so authenticated users keep current fix/access/caution posture visible even on the policy routes instead of dropping back to weekly pulse only.
    - hosted verification and in-process smoke stayed green after the controller-plus-smoke carry-through.
  - `chummer.run-services` / `chummer6-hub` `5d4b057a` `Deepen recap shelf publication continuity`
    - signed-in home and account recap-shelf views now keep linked creator-publication visibility, discovery posture, lineage, return truth, support closure, and direct build-path follow-through visible instead of compressing recap output back to trust-plus-next-step prose outside the publication detail card.
    - hosted verification and in-process smoke stayed green after the recap-shelf continuity carry-through.
  - `chummer.run-services` / `chummer6-hub` `879e2b76` `Add signed-in artifact shelf continuity`
    - the public `/artifacts` route now grows a signed-in overlay that reuses governed recap-shelf and creator-publication truth so personal, campaign, and creator views can be browsed from one artifact route with deduped artifact identity instead of forcing a jump straight back to deeper account pages.
    - hosted verification and in-process smoke stayed green after the signed-in artifact-shelf continuity slice.
  - `chummer.run-services` / `chummer6-hub` `d00201af` `Link detail pages back to signed-in artifact shelf`
    - live-proof, roadmap, and preview-concept detail pages now point signed-in users back to the signed-in artifact shelf, so the new personal/campaign/creator continuity rail is reachable from deeper detail routes instead of being stranded on `/artifacts` only.
    - hosted verification and in-process smoke stayed green after the detail-page follow-through slice.
  - `chummer.run-services` / `chummer6-hub` `a265eaea` `Expose starter lane on the landing page`
    - the authenticated public landing surface now derives a starter-lane card from the same signed-in campaign spine truth used on home/account, showing legal-runner, understandable-return, campaign-ready, next-step, and evidence posture plus direct routes into `/home/work` and the bounded first-session proof drawer instead of leaving the front door blind to milestone `19`.
    - hosted verification and in-process smoke stayed green after the landing-model, Razor, and smoke updates.
  - `chummer.run-services` / `chummer6-hub` `270f63c7` `Deepen landing starter lane trust follow-through`
    - the authenticated front-door starter lane now also reuses signed-in fix-availability and current-caution rows plus a direct install-support route, so onboarding reuses live trust/support truth instead of stopping at campaign proof alone.
    - hosted verification and in-process smoke stayed green after the trust-copy carry-through.
  - `chummer.run-services` / `chummer6-hub` `6141ba12` `Deepen account starter lane trust follow-through`
    - the selected first-playable-session drawer on account work now reuses signed-in fix-availability and current-caution truth plus a direct install-support route, so deeper onboarding follow-through no longer drops back to campaign proof only after the front door picked up the same trust/support rails.
    - hosted verification and in-process smoke stayed green after the account-view carry-through.
  - `chummer-hub-registry` `2965744` `Refresh design mirror after public guide sync`
    - the registry mirror now carries the refreshed public-guide export manifest after the editorial-canon publish.
  - `chummer-media-factory` `11e1ee9` `Refresh design mirror after public guide sync`
    - the media-factory mirror now carries the refreshed public-guide export manifest after the editorial-canon publish.
  - `chummer-design` `WEEKLY_PRODUCT_PULSE` `Local generator and pulse mirror sync for public trust surface`
  - the pulse generator now emits `closure_health`, `adoption_health`, and `progress_trend` from fleet journey-gates, support packets, status plane, and local release proof.
  - this same enriched pulse was mirrored into `chummer6-hub`, `chummer6-hub-registry`, `chummer.run-services`, and all manifest mirrors currently in scope.
  - No canon status change was required after these slices; `chummer-design` still correctly leaves milestone `16` as `in_progress`.

## Current pushed baseline

- `chummer.run-services` / `chummer6-hub`: `6141ba12`
- `chummer-hub-registry`: `2965744`
- `chummer6-ui`: `6ffc0893`
- `chummer6-mobile`: `c7afeda`
- `chummer-design`: `b1451c2`
- `Chummer6`: `e2c5928`
- `EA`: `10af073`
- `chummer6-core`: `07f3ba8e`
- `chummer-ui-kit`: `f5c49c7`
- `chummer-media-factory`: `11e1ee9`

## Repo state snapshot

Clean now:

- `/docker/chummercomplete/chummer-hub-registry`
- `/docker/chummercomplete/chummer6-mobile`
- `/docker/chummercomplete/chummer6-ui`
- `/docker/chummercomplete/chummer6-hub`
- `/docker/chummercomplete/chummer6-core`
- `/docker/chummercomplete/chummer-ui-kit`
- `/docker/chummercomplete/Chummer6`
- `/docker/fleet/repos/chummer-media-factory`

Concurrent unrelated dirt intentionally left in place:

- `/docker/fleet`
  - `.codex-design/product/PUBLIC_FAQ_REGISTRY.yaml`
  - `.codex-design/product/PUBLIC_RELEASE_EXPERIENCE.yaml`
  - `.codex-design/product/PUBLIC_TRUST_CONTENT.yaml`
- `/docker/EA`
  - `.codex-design/product/PUBLIC_GUIDE_EXPORT_MANIFEST.yaml`
  - `chummer6_guide/VISUAL_PROMPTS.md`
  - `scripts/chummer6_guide_canon.py`
  - `scripts/chummer6_guide_media_worker.py`
  - `tests/test_chummer6_guide_canon.py`
  - `tests/test_chummer6_guide_media_worker.py`
- `/docker/chummercomplete/chummer.run-services`
  - `.codex-design/product/PUBLIC_FAQ_REGISTRY.yaml`
  - `.codex-design/product/PUBLIC_PART_REGISTRY.yaml`
  - `.codex-design/product/PUBLIC_TRUST_CONTENT.yaml`
  - `.codex-design/product/horizons/alice.md`
  - `.codex-design/product/horizons/ghostwire.md`
  - `.codex-design/product/horizons/jackpoint.md`
  - `.codex-design/product/horizons/karma-forge.md`
  - `.codex-design/product/horizons/knowledge-fabric.md`
  - `.codex-design/product/horizons/local-co-processor.md`
  - `.codex-design/product/horizons/nexus-pan.md`
  - `.codex-design/product/horizons/runbook-press.md`
  - `.codex-design/product/horizons/runsite.md`
  - `.codex-design/product/horizons/table-pulse.md`
  - `Chummer.Run.AI/Program.cs`
  - `scripts/ai/run_codex.sh`
  - `scripts/ai/run_codex_resume.sh`
- `/docker/chummercomplete/chummer-design`
  - `products/chummer/HORIZON_REGISTRY.yaml`
  - `products/chummer/PUBLIC_FAQ_REGISTRY.yaml`
  - `products/chummer/PUBLIC_GUIDE_EDITORIAL_COVERS.yaml`
  - `products/chummer/PUBLIC_PART_REGISTRY.yaml`
  - `products/chummer/PUBLIC_RELEASE_EXPERIENCE.yaml`
  - `products/chummer/PUBLIC_TRUST_CONTENT.yaml`
  - `products/chummer/horizons/*`
  - `products/chummer/public-guide*`
  - `scripts/ai/materialize_public_guide_bundle.py`
  - `scripts/ai/verify.sh`
  - `scripts/ai/validate_public_guide_editorial_covers.py`

## Verification completed in this session

- `chummer-hub-registry`
  - `bash scripts/ai/verify.sh`
  - `git diff --check`
- `chummer.run-services`
  - `bash scripts/ai/build_r1_cleanroom.sh`
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
- `chummer6-ui`
  - `bash scripts/ai/verify.sh`
  - targeted `git diff --check`
- `chummer-design`
  - `bash scripts/ai/verify.sh`
- `Chummer6`
  - `bash scripts/verify_public_guide.sh`
- `chummer-media-factory`
  - `bash scripts/ai/verify.sh`
  - `git diff --check`

## What changed materially

1. Registry artifact truth is now explainable on every main read model and can carry the full governed publication posture downstream.
   Search, preview, and projection all expose audience, ownership posture, latest publication state, latest publication trust band, latest publication trust/discovery/lineage summaries, discoverability posture, and latest next safe action from one artifact record, and both publication lists and artifact shelves can now be filtered directly by governed posture instead of client-side ad hoc filtering.

2. Hosted publication surfaces are materially more consistent.
   Signed-in home now exposes aftermath ownership plus publication state, creator-publication discovery plus status, and a direct route back to the related build path, while the account publication list now shows both publication state and the same build-follow-through route instead of forcing detail-card hops.

3. Install-specific trust status is more explicit on signed-in trust surfaces.
   Downloads, help, and now all expose per-install fix availability plus a current-caution row, and the caution lane now de-escalates automatically once the linked install reaches the verification-ready build.

4. Public trust posture now carries the whole governed weekly pulse on the front door without template drift.
   Downloads, help, and now surface adoption health inside the install-specific trust panel, and the public landing trust pulse now renders access posture, release proof, launch readiness, adoption health, closure health, progress trend, provider-route stewardship, journey pulse, and caution from the shared row collection instead of leaving those signals hidden behind the model or a hand-picked subset.

5. First-session onboarding proof is now materially richer across hosted home and account routes.
   The bounded first playable session projection now exposes legal-runner, understandable-return, and campaign-ready summaries from grounded rule environment, continuity, claimed-device return, and readiness cues, and signed-in home/account surfaces repeat that proof on shared campaign cards, selected-workspace detail, and the calmer lead first-session card instead of forcing users to infer it from one generic summary line.

6. First-session proof and artifact-shelf continuity are now embodied on mobile follow-through too, not only on hosted or one recap paragraph.
   Mobile workspace-lite now renders explicit legal-runner, understandable-return, and campaign-ready proof from the same grounded runtime/continuity/readiness posture, and its recap lane now carries publication trust ranking, discoverability posture, creator-publication lineage, explicit personal/campaign/published browse targets, and the next step instead of stopping at publication state alone.

7. Starter build kits now carry grounded first-session guidance from core, and mobile trust posture now has an explicit caution lane.
   Core build-kit details/install previews now describe how starter lanes reach the first playable session and return safely into campaign continuity, while mobile workspace-lite surfaces explicitly state the current caution lane instead of implying it through support prose alone.

8. Media-factory now preserves creator-publication identity, trust posture, lineage, and governed status inside the packet plan itself.
   Publication packets carry the creator publication id as a governed anchor, and evidence labels explicitly name provenance, trust band, discoverability, discovery, lineage, ownership, and state.

9. Downstream smoke and repo-local verification now guard the richer onboarding, trust, caution, lineage, and shelf-audience contracts.
   Search/preview smoke covers ownership posture and publication-state carry-through, hosted publication surfaces are guarded across home and account list/detail views, downstream smoke now proves registry shelf-audience filters, and media/mobile verifiers enforce creator-publication lineage carry-through.

10. Desktop trust, support, update, access, and recovery parity is materially deeper.
   `chummer6-ui` now has real top-level native surfaces for update posture, support follow-through, tracked support cases, device/access state, report issue, and crash recovery, with persistent shell navigation and preference-backed return state instead of burying those W4 flows behind one home summary surface.

11. Canonical public-guide editorial output and downstream mirrors are resynced.
   `chummer-design` now carries the refreshed editorial-cover registry, curated source plates, bundle generators, and export manifest, `Chummer6` mirrors the new public guide bundle, and the `fleet`, `chummer6-hub`, `chummer-hub-registry`, and `chummer-media-factory` design mirrors all carry the refreshed manifest instead of drifting behind the latest design canon.

12. Desktop onboarding proof now reaches the native home cockpit too.
   `chummer6-ui` now carries first playable session proof and starter-lane next-step/evidence through both the desktop server-plane DTO and the desktop home campaign projector, so desktop no longer depends on hosted or mobile-only first-session proof when milestone `19` is the active follow-through lane.

13. Desktop artifact shelf posture now keeps trust ranking and bounded discoverability visible.
   `chummer6-ui` now carries recap-shelf trust posture onto the native home cockpit, so desktop no longer drops creator-publication trust down to publication state after hosted/mobile already proved the richer artifact shelf.

14. Desktop creator-publication continuity now keeps visibility, lineage, and next-step posture too.
   `chummer6-ui` now carries richer creator-publication continuity onto the native home cockpit, so desktop no longer stops at provenance/trust while hosted and mobile already surface lineage and follow-through.

15. Desktop artifact shelf browsing is now first-class instead of prose-only.
   `chummer6-ui` now gives linked installs direct native-home actions for `My stuff`, `Campaign stuff`, and `Published stuff`, and the campaign server-plane highlights explicitly state that those views stay browseable from one governed shelf.

16. The authenticated front door now carries a governed starter lane instead of stopping at trust and proof shelves.
   `chummer.run-services` now derives a signed-in landing starter-lane card from the same campaign spine first-session truth used on home/account, so the public front door can send a user straight into legal-runner, understandable-return, campaign-ready follow-through without tutorial folklore or repo knowledge.

17. Front-door starter-lane onboarding now reuses live trust and support truth too.
   The signed-in landing starter-lane card now pulls `Fix availability`, `Current caution`, and install-support follow-through from the shared trust/support rails instead of leaving milestone `19` to rest on campaign proof only.

18. Account work first-session follow-through now keeps the same trust and support rails.
   The selected first-playable-session drawer on account work now also carries `Fix availability`, `Current caution`, and install-support follow-through from the signed-in trust panel, so onboarding depth stays on one governed support lane instead of fragmenting after the front door.

## Next likely frontier

Do not reopen the already-landed registry or signed-in-home slices unless a new regression appears.

The next useful re-derivation should come from `chummer-design` and continue W3/W4 depth in the cleanest remaining seams:

- `chummer.run-services` / `chummer6-hub`
  - live `main` is now at `a265eaea`; re-derive from that head and keep pushing public/account/operator trust posture, publication continuity, and first-session follow-through until milestones `15`, `18`, and `19` no longer depend on deeper account-only views or single-card detail paths
  - signed-in trust and fix-readiness truth now survive the public landing front door, downloads/help/now, contact submission, home, account, download handoff, privacy/terms policy routes, the richer recap-shelf publication chain, a signed-in `/artifacts` surface with explicit `all`/`personal`/`campaign`/`creator` browsing plus dossier-backed personal entries, the deeper live-proof/roadmap/preview detail routes that point back to that shelf, the new first-class `/status` route, and a signed-in landing starter-lane card that routes directly into `/home/work` and bounded first-session proof, so the next clean seam should move outward again: public/account/operator routes that still stop before registry-backed trust/discovery/lineage explanation, or another W3/W4 hosted surface outside the already-green trust/download/status/artifact-view/starter-lane chain
- `chummer-hub-registry`
  - continue from `2965744` by carrying the new shelf-audience filter deeper wherever personal, campaign, creator, and retained-history browsing is still implicit instead of first-class, especially any downstream consumers that still re-filter locally
- `chummer-media-factory`
  - continue from `11e1ee9` by threading the now-labeled creator-publication lineage/trust anchors into any downstream packet/render surfaces that still treat publication posture as implicit
- `chummer6-mobile`
  - the next clean seam is deeper publication/trust carry-through beyond the new caution, onboarding, recap-trust, recap-lineage, and browse-view lanes, especially anywhere creator-publication posture still stops at state/next-step without explicit recommendation or caution posture
- `chummer6-ui`
  - live `fleet/ui` is now at `6ffc0893`; desktop home now carries grounded first-session proof, artifact/publication continuity posture, and direct governed artifact-shelf browse actions, so the next clean seam should move past onboarding/artifact/publication parity into remaining deeper trust/operator follow-through that still lacks the same governed posture on desktop
- `chummer-design` / `Chummer6`
  - the editorial public-guide bundle and downstream sync are still concurrently active, while `/status` is now explicit in canon navigation and landing manifest truth; the next canon-facing slice should come from still-open W3/W4 product truth, not from reopening the already-landed status-route or cover/asset refresh

The main rule for the next session is unchanged: re-derive from `chummer-design`, not from the last clean repo boundary.
