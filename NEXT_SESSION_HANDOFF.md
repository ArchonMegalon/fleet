# Next Session Handoff

Date: 2026-03-31
Workspace focus: `/docker/fleet`, `/docker/EA`, `/docker/chummercomplete/*`, `/docker/fleet/repos/*`, `/docker/chummer5a`

## Handoff refresh (2026-03-31 latest cross-repo sync)

- 2026-03-31: milestone `14` UI fixtures and showcase copy now track the shared-publication wording that Hub, media-factory, and registry already emit.
  - `chummer6-ui` `b9ce13c8` `feat: align publication fixtures with shared wording`
    - presentation test fixtures and the Blazor home showcase sample now expect `campaign packet` / `publication shelf` / `publication status` wording instead of the earlier creator-packet phrases that Hub no longer emits.
    - desktop presentation verification stayed green via `cd /docker/chummercomplete/chummer6-ui && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `14` follow-through is likely a broader cross-surface audit rather than another obvious single-string seam: the remaining work appears to be finding any residual creator-audience language that is still semantically correct for milestone `13` discovery versus any wording that should move to shared-publication framing for milestone `14`.

- 2026-03-31: milestone `14` registry artifact search / preview / projection summaries now use shared-publication shelf language instead of describing the multi-kind public route as a creator-publication lane.
  - `chummer6-hub-registry` `8e0368e` `feat: align artifact shelves with shared publications`
    - registry-owned search, preview, and projection shelf summaries now describe `shared publication shelves` and the `shared publication lane` for published replay, recap, and other governed artifacts, while keeping the existing creator-scoped audience filter semantics intact.
    - registry verification now locks in the shared-publication shelf wording across search, preview, replay-package preview, and post-publication projection flows.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer-hub-registry && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `14` follow-through is likely UI-side: desktop/account/public copy still contains creator-audience naming in places where the route is now explicitly shared-publication, especially anywhere presentation layers talk about creator shelf posture instead of the shared publication shelf while still consuming the same governed projections.

- 2026-03-31: milestone `14` shared-publication wording now reaches the Hub projection layer itself, so recap-safe publication summaries, discovery posture, moderation posture, and support copy stop falling back to creator-only packet language before registry review starts.
  - `chummer.run-services` / `chummer6-hub` `f229e977` `feat: align shared publication projection copy`
    - campaign-spine and workspace server-plane publication summaries now refer to the publication shelf / shared publication route instead of creator-packet rails, and registry-backed next-step / moderation / discovery strings now talk about publication comparison and public discovery rather than creator-only shelves.
    - the recap-safe publication summary on home/account now follows the same shared-publication language, and the lingering nullable warnings in `CampaignSpineService` are gone because creator-linked provenance and audit summaries now use null-safe accessors.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer.run-services && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `14` follow-through is to align registry artifact search / preview ownership summaries with the same shared-publication vocabulary, because registry shelf projections still talk about a creator publication lane even after the public route, packet generation, draft evidence, and Hub projections all moved to shared-publication framing.

- 2026-03-31: milestone `14` registry-owned draft and moderation evidence now speak in shared-publication terms instead of assuming every governed lane is a creator packet.
  - `chummer.run-services` / `chummer6-hub` `75e5f9bf` `feat: enrich shared publication registry drafts`
    - the Hub registry bridge now stamps publication kind, status, visibility, and discovery into generated draft descriptions, and default submit/approve/reject/publish notes now keep shared-publication wording when the operator leaves the notes blank.
    - account/work publication detail smoke coverage now requires that registry-owned draft detail carries publication-kind and publication-status evidence instead of only a generic summary blob.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer.run-services && bash scripts/ai/verify.sh`.
  - `chummer6-hub-registry` `3e41c68` `feat: default shared publication review notes`
    - registry-owned draft submission, approval, rejection, and publish flows now default to shared-publication review/follow-through/discovery notes, and the latest moderation note now updates on publish instead of reusing the prior approval note.
    - registry verification now locks in the default shared-publication note path when callers omit explicit moderation or publish notes.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer-hub-registry && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `14` follow-through is to scrub the remaining creator-only projection summaries in `CampaignSpineService` and `CampaignWorkspaceServerPlaneService`, so publication summary, return, support, and watchout copy on recap-safe items stays aligned with the shared-publication route even before registry review starts.

- 2026-03-31: milestone `14` generated publication packets now follow the shared-publication route instead of preserving creator-only packet wording after the Hub route and surface framing changed.
  - `chummer-media-factory` `6b02da1` `feat: align packet evidence with shared publications`
    - `CreatorPublicationPlannerService` now emits explicit publication kind evidence, generic `Publication status` / `Public publication` attachment labels, shared-publication ownership and output-lane wording, and `share_public_publication` follow-through when a governed publication is already live.
    - media-factory verification fixtures now mirror the same campaign-packet/shared-publication posture, so generated evidence no longer claims every public lane is a creator packet once campaign, dossier, recap, replay, and run-module lanes fan out from shared artifact truth.
    - owner-repo verification stayed green via `cd /docker/fleet/repos/chummer-media-factory && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `14` follow-through is to carry the same shared-publication framing into registry draft descriptions and moderation/publish note generation, so registry-owned review receipts stop defaulting to creator-only lane language now that public publication is multi-kind.

- 2026-03-31: milestone `14` shared publication flow now fans recap-safe artifact truth into multiple governed publication lanes, and the live public/account routes no longer frame that lane as creator-only packet output.
  - `chummer.run-services` / `chummer6-hub` `862ea9d3` `feat: fan out shared artifact publication lanes`
    - campaign spine and workspace server-plane now synthesize multiple governed publication records directly from recap-shelf truth instead of collapsing a workspace down to one creator-shaped packet.
    - stable per-artifact publication ids, kind-aware titles and summaries, and per-item trust, discoverability, audience, ownership, provenance, and audit linkage now stay attached to replay, dossier, campaign, run-module, and recap-safe entries on the same shared publication rail.
  - `chummer.run-services` / `chummer6-hub` `e5f2d24c` `feat: frame shared publications on public routes`
    - public `/artifacts`, shared public publication detail, signed-in `/home`, and `/account/work/publications/{id}` now describe the route as governed publication discovery and shared publications instead of hard-coding creator-packet language after the route became multi-kind.
    - hub smoke coverage now asserts the shared-publication framing and the public publication inspect link on the live public/account surfaces.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer.run-services && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `14` follow-through is to carry the same shared-publication framing and kind-specific posture into media-factory packet generation and registry draft/moderation evidence, so generated publication packets and moderation notes stop defaulting to creator-packet language once campaign, dossier, replay, and run-module lanes are live.

- 2026-03-31: milestone `14` is now in progress because discoverable publication traffic no longer dead-ends on a creator-only public route, and the governed publication detail lane now preserves concrete shared project kinds instead of collapsing back to generic build-idea fallback.
  - `chummer.run-services` / `chummer6-hub` `4f460af2` `feat: unify public publication detail lanes`
    - discoverable publication links now target `/artifacts/publications/{publicationId}` as the shared public publication route, while legacy `/artifacts/creator/{publicationId}` requests redirect into that shared detail lane for compatibility.
    - signed-in account publication detail now surfaces `Publication kind` plus registry `Draft kind`, and the Hub registry bridge preserves concrete shared project kinds like campaign, dossier, run-module, primer, replay, and recap when it builds governed draft requests from shared artifact truth.
    - hub Playwright, live-audit, and source-guard smoke coverage now prove the shared public publication route plus kind surfacing instead of hardcoding the older creator-only route.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer.run-services && bash scripts/ai/verify.sh`.
  - `chummer-media-factory` `4c832df` `feat: align publication packets with shared public route`
    - creator-publication packet evidence now emits the shared public publication route (`/artifacts/publications/{publicationId}`) so media follow-through stays aligned with the same governed publication path Hub renders.
    - owner-repo verification stayed green via `cd /docker/fleet/repos/chummer-media-factory && bash scripts/ai/verify.sh`.
  - `chummer-design` `1b94c0b` `chore: mark module publication flow in progress`
    - `NEXT_20_BIG_WINS_AFTER_POST_AUDIT_CLOSEOUT_REGISTRY.yaml` now marks milestone `14` as `in_progress` in both canonical design and the Fleet mirror.
  - the next meaningful milestone `14` follow-through is to stop synthesizing only one workspace-level creator packet and instead project multiple governed publication lanes directly from shared dossier/campaign/run-module artifact truth, so the shared route carries more than one creator-shaped publication record.

- 2026-03-30: milestone `13` public creator discovery now has a true compare-at-a-glance lane instead of forcing visitors to open each published packet detail page one at a time.
  - `chummer.run-services` / `chummer6-hub` `eccc9ac8` `feat: compare live creator packets on shelf`
    - public `/artifacts` now renders a ranked `Compare at a glance` creator-discovery rail that reuses provenance, trust, compare-by, lineage, moderation, and return posture from the governed creator-publication projection instead of inventing a second comparison model.
    - the public creator card stack now follows the same governed comparison order as the compact comparison rail, and hub Playwright plus live-audit verification now require that compare-at-a-glance copy on `/artifacts`.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/verify.sh`.
  - note: the user prompt still named milestones `3` through `7` as the active frontier, but the canonical registry and this handoff already mark milestones `3`, `4`, `5`, `6`, and `7` complete as of 2026-03-30; the real active frontier remains W3 milestone `13` depth plus milestone `14` runbook/module publication work.

- 2026-03-30: milestone `13` owner-facing account/work publication surfaces now expose the same live public creator packet that discovery users see, without dropping the private moderation lane.
  - `chummer.run-services` / `chummer6-hub` `113c3d41` `feat: expose public creator packets on account`
    - signed-in `/account/work/publications/{id}` now keeps `Open public creator packet` alongside the governed private publication-status route once that packet is actually published and discoverable.
    - owner-facing account/work creator-publication lists plus linked recap shelves now offer the same public inspect link for live discoverable packets, while unpublished packets still stay on the private moderation rail only.
    - hub Playwright and live-audit verification now follow that optional public account-surface link when it exists, while still proving the private publication detail and build-handoff flow remain intact.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `13` follow-through is to add a true compare-at-a-glance surface on the public creator-discovery shelf, so multiple live creator packets can be evaluated against each other without opening each detail page one by one.

- 2026-03-30: milestone `13` public creator discovery is now guarded by the hosted audit stack, and signed-in `/artifacts` keeps live creator packets on that same public inspect rail instead of bouncing them back to private moderation status.
  - `chummer.run-services` / `chummer6-hub` `cde8902d` `feat: verify public creator packet rails`
    - signed-in `/artifacts` now routes published discoverable creator cards and linked recap entries through `/artifacts/creator/{publicationId}` when the packet is genuinely live, while unpublished packets still keep the private `/account/work/publications/{id}` moderation fallback.
    - `scripts/e2e-hub-playwright.cjs` and `scripts/hub-live-audit.py` now extract and verify the public creator-discovery detail route directly, and signed-in home verification now accepts either the public creator packet rail or the private publication-status rail based on actual publication posture instead of hardcoding the old private-only path.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `13` follow-through is to let owner-facing account/work publication surfaces expose the same public inspect route alongside moderation status once a creator packet is live, so signed-in owners do not have to bounce between separate discovery and governance lanes to compare what the public can actually see.

- 2026-03-30: milestone `13` live public creator packets now stay on the public inspect rail from more of the product, and media-factory packets recognize that live public route too.
  - `chummer.run-services` / `chummer6-hub` `f158936b` `feat: route live creator packets through public detail links`
    - signed-in `/home/work` now routes discoverable published creator packets and linked aftermath creator-publication follow-through to `/artifacts/creator/{publicationId}` instead of always falling back to the private account-status route; unpublished packets still keep the account-route fallback.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/verify.sh`.
  - `chummer-media-factory` `315bfc6` `feat: emit public creator packet follow-through`
    - `CreatorPublicationPlannerService` now emits `Public creator packet` attachments, a public `/artifacts/creator/{publicationId}` evidence line, and `share_public_creator_packet` next-action posture when a creator packet is already published and discoverable, instead of treating every packet as pre-public status follow-through.
    - owner-repo verification stayed green via `cd /docker/fleet/repos/chummer-media-factory && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `13` follow-through is to add a direct public comparison surface or richer grouping/sorting on the creator-discovery shelf so multiple live creator packets can be evaluated against each other without manual card-by-card inspection.

- 2026-03-30: milestone `13` published creator packets now have a first-class public inspect route instead of stopping at the public `/artifacts` shelf teaser.
  - `chummer.run-services` / `chummer6-hub` `35974e9a` `feat: add public creator publication detail routes`
    - public `/artifacts/creator/{publicationId}` now loads discoverable creator packets from the same governed creator-publication projection used on signed-in surfaces, keeping provenance, trust, discovery, comparison, lineage, moderation-watch, return, support, and next-step posture on one public route.
    - public creator-discovery cards on `/artifacts` now deep-link into that dedicated inspect route, so milestone `13` public discovery no longer dead-ends at shelf summary copy alone.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `13` follow-through is to add a direct public comparison surface or richer shelf sorting/grouping so multiple discoverable creator packets can be evaluated against each other without relying only on per-packet detail pages.

- 2026-03-30: milestone `13` creator publication can now move from approval-backed account follow-through onto live public creator discovery without leaving the governed draft lane.
  - `chummer6-hub-registry` `5e46410` `feat: publish approved creator drafts`
    - the registry-owned publication-draft workflow now has an explicit publish transition on `/api/v1/publication-drafts/{draftId}/publish`, records published timestamps and published artifact-receipt versions, and keeps the same draft/detail/receipt lane authoritative when approval-backed creator packets become live discovery instead of freezing forever at `approved_for_publication`.
    - registry verification stayed green via `cd /docker/chummercomplete/chummer-hub-registry && bash scripts/ai/verify.sh`.
  - `chummer.run-services` / `chummer6-hub` `3a3af6fc` `feat: publish creator packets onto public discovery`
    - signed-in `/account/work/publications/{id}` now exposes an explicit publish action after approval, the shared creator-publication projection promotes to `published` with discoverable `curated-live` trust posture, and signed-in home plus linked recap shelf entries inherit that live posture from the same registry receipt instead of stalling on approval-backed state.
    - public `/artifacts` now includes a governed creator-discovery rail backed by the same creator-publication projections, so guest and signed-in viewers can inspect published creator packets with provenance, trust, comparison, lineage, moderation-watch, and next-step posture without a second public shadow model.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `13` follow-through is to deepen public comparison/detail surfaces beyond the `/artifacts` discovery shelf so discoverable creator packets can be compared and inspected directly without relying on signed-in account detail routes.

- 2026-03-30: milestone `13` registry-backed creator-publication posture now flows onto the shared hosted creator-publication projection instead of stopping at the account detail side-panel.
  - `chummer.run-services` / `chummer6-hub` `605b6872` `feat: carry registry publication state onto shared creator projections`
    - `CampaignSpineService` now overlays registry publication receipts onto the shared `CreatorPublicationProjection`, so home/account creator-publication cards and the linked recap shelf inherit approved, pending-review, and rejected posture from the registry-owned draft workflow instead of staying on synthetic `preview_ready` status once moderation starts.
    - signed-in account detail now keeps the same approved moderation note and receipt rail on both the registry detail block and the shared creator-publication card, while signed-in home now proves the same governed approval posture on the shared creator-publication list and the linked recap shelf entry.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `13` follow-through is to widen the same registry-backed moderation and receipt posture onto the remaining public/discovery/comparison surfaces that still derive creator-publication ranking from synthetic hosted state rather than the registry-owned review lane.

- 2026-03-30: milestone `13` registry-backed creator-publication moderation now reaches the signed-in account detail route instead of stopping at registry APIs and synthetic hosted preview posture.
  - `chummer.run-services` / `chummer6-hub` `e334996a` `feat: govern creator publication review on account`
    - signed-in `/account/work/publications/{id}` now auto-projects the registry draft and receipt, shows moderation case/status/notes, and exposes governed submit, approve, and request-changes actions on the same account surface instead of leaving moderation flow implied by trust summary prose alone.
    - `CreatorPublicationRegistryBridge` keeps the hosted account view attached to the registry-owned draft id, moderation case, and artifact receipt without inventing a parallel hosted publication-state model.
    - hosted verification and smoke are green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/verify.sh`; smoke now proves the detail route starts with a registry draft, enters pending review after submit, and lands approved moderation notes after approval.
  - `chummer.run-services` / `chummer6-hub` `79c7bb37` `fix: register publication draft workflow in hub`
    - the live Hub app host now registers `IHubPublicationDraftService` / `HubPublicationDraftService` in DI, so the new account moderation route resolves in the real runtime and not only in direct controller test wiring.
    - re-verified green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `13` follow-through is to carry the same registry moderation and receipt posture onto broader signed-in/public creator-publication shelves and discovery/comparison surfaces so trust ranking deepens beyond the account detail route.

- 2026-03-30: milestone `13` creator-publication trust/comparison/moderation posture now survives hosted projections, calmer signed-in/public surfaces, and media-factory creator packets instead of stopping at trust-band shorthand.
  - `chummer.run-services` / `chummer6-hub` `9e9574e1` `feat: deepen creator publication trust posture`
    - `CreatorPublicationProjection` now carries explicit `TrustSummary`, `ComparisonSummary`, and `ModerationSummary`, and the hosted campaign spine derives them from governed publication status/visibility instead of leaving discovery/trust posture implicit.
    - signed-in `/home/work`, `/account/work`, `/account/work/publications/{id}`, and signed-in `/artifacts` now surface creator-publication trust posture, compare-by guidance, and moderation posture on both the primary publication cards and the linked replay/recap shelf snippets, so milestone `13` discovery and comparison no longer flatten into trust-band plus next-step shorthand.
    - hosted verification stayed green via `cd /docker/chummercomplete/chummer.run-services && bash scripts/ai/run_services_verification.sh` and `cd /docker/chummercomplete/chummer.run-services && bash scripts/ai/run_services_smoke.sh`.
  - `chummer-media-factory` `43ecde7` `feat: preserve creator publication trust posture`
    - `CreatorPublicationPlannerService` now preserves the same trust posture, compare-by guidance, and moderation summary in creator-packet evidence lines, so review formatting no longer strips milestone `13` comparison and moderation reasoning back to provenance/discovery only.
    - owner-repo verification stayed green via `cd /docker/fleet/repos/chummer-media-factory && bash scripts/ai/verify.sh`.

- 2026-03-30: milestone `13` now has a real registry-owned publication-draft and moderation queue seam instead of forcing creator-publication follow-through to start from synthetic hosted-only preview posture.
  - `chummer6-hub-registry` `b9d9a72` `feat: add publication draft workflow`
    - `HubPublicationDraftsController` plus `HubPublicationDraftService` now expose registry-owned draft create/list/detail/update/archive/delete flows, draft submission receipts, moderation queue listing, approval/rejection decisions, and publication receipts on `/api/v1/publication-drafts`.
    - registry runtime wiring and verify coverage now prove the end-to-end draft lane, and the service-side compile fix inside that feature also cleared the hosted cleanroom blocker that had been breaking `chummer.run-services` owner verification.
    - owner-repo verification stayed green via `cd /docker/chummercomplete/chummer-hub-registry && bash scripts/ai/verify.sh`.
  - the next meaningful milestone `13` follow-through from here is to replace the still-synthetic hosted `preview_ready` creator-publication posture with real registry-backed publication-draft creation, moderation state, and receipt linkage on the same home/account/artifact flows.

- 2026-03-30: milestone `12` is now closed in owner canon and the Fleet mirror, and the next active W3 frontier is milestone `13` creator-publication depth.
  - `chummer-design` `dc8f541` `docs: close milestone 12 artifact lane`
    - `NEXT_20_BIG_WINS_AFTER_POST_AUDIT_CLOSEOUT_REGISTRY.yaml` now marks milestone `12` complete, promotes milestone `13` to `in_progress`, and refreshes the generated progress history/report plus weekly product pulse so the public planning layer agrees with the repo-local replay/recap artifact evidence.
    - verified via `cd /docker/chummercomplete/chummer-design && bash scripts/ai/materialize_weekly_product_pulse.sh && python3 scripts/ai/publish_local_mirrors.py && bash scripts/ai/verify.sh`.
  - `chummer.run-services` / `chummer6-hub` `1a40dd09` `feat: carry replay artifacts onto signed-in shelves`
    - signed-in `/artifacts`, shared campaign summaries, and calmer home/account return language now keep replay artifacts visible as replay-safe return outputs instead of recap-only prose once the replay package reaches the richer shelf.
    - hosted smoke now proves replay artifacts survive the signed-in all/campaign/creator shelf filters with creator-publication linkage intact.
  - milestone `13` is now the next meaningful repo-local lane: creator publication v3 still needs deeper discovery, lineage, moderation, and trust-ranking posture beyond the replay/recap artifact closure that just landed.

- 2026-03-30: milestone `12` now issues replay timelines from the same durable hosted aftermath rail instead of limiting the governed package seam to recap/report/downtime packets.
  - `chummer.run-services` / `chummer6-hub` `db3c2c5e` `feat: issue replay timelines from the aftermath rail`
    - `CampaignWorkspaceServerPlaneService` now accepts replay generation on the existing aftermath package endpoint, the workspace server plane now emits explicit `replay_package` change packets, and replay packages keep the same registry artifact provenance/audit seam as recap packages instead of falling back to a recap-only issuance path.
    - signed-in `/account/work/workspaces/{id}` now exposes replay generation from the same governed aftermath package form, broadens recap-only copy to aftermath/replay wording, and keeps replay packets on the richer return shelf on the shared campaign card.
    - signed-in `/home/work` now labels the lead aftermath card from package kind, so replay timelines surface as replay-safe follow-through instead of being misdescribed as recap-only output when they become the latest governed package.
    - hosted verification is green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_verification.sh` and `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_smoke.sh`.
  - this hosted issuance slice fed the milestone `12` closeout recorded above; replay timelines are now part of the closed artifact lane rather than an open recap-only follow-through gap.

- 2026-03-30: milestone `12` replay-safe follow-through now survives the mobile return shell and media-factory creator-packet formatter instead of stopping at hosted issuance.
  - `chummer6-mobile` `2752b93` `feat: surface replay-safe package follow-through`
    - workspace-lite and the live play shell now expose replay-safe summary, audience, ownership, publication, provenance, audit, lineage, and next-step posture beside the existing recap-safe packet, so the claimed-device return lane can explain contested-turn review without flattening replay back into recap-only copy.
    - travel posture, offline-prefetch posture, campaign memory, and follow-through labels now keep replay timeline and recap packet carry-forward side by side on the same install-local return lane instead of only naming the recap packet.
    - verified via `cd /docker/chummercomplete/chummer6-mobile && bash scripts/ai/verify.sh`.
  - `chummer-media-factory` `eb8d5ac` `fleet(media-factory): title: Finish milestone coverage modeling for media-factory so ETA and…`
    - `CreatorPublicationPlannerService` now preserves output kind, ownership, publication, next-safe-action, provenance, and audit posture for replay and recap outputs inside the governed creator packet instead of recap-only evidence lines.
    - runtime verification now proves replay-safe creator packets keep replay artifact references plus replay-specific formatting evidence (`Output kind`, `Output ownership`, `Output publication`, `Output next safe action`, `Output provenance`, `Output audit`) through review formatting.
    - verified via `cd /docker/fleet/repos/chummer-media-factory && bash scripts/ai/verify.sh`.
  - this downstream mobile/media slice fed the milestone `12` closeout recorded above; replay-safe return and formatting proof are now part of the closed artifact lane.

- 2026-03-30: milestone `12` recap provenance now survives hosted shelf projection, mobile return-shell follow-through, and media-factory creator-packet formatting instead of stopping at the durable hosted artifact record.
  - `chummer.run-services` / `chummer6-hub` `43bc49af` `Persist recap packages as registry artifacts`
    - the hosted `main` head already carries recap-shelf provenance/audit on the calmer shared return surfaces: signed-in `/home`, `/account/work/workspaces/{id}`, and `/artifacts` all now keep the same recap provenance/audit language attached to the shared shelf entry instead of flattening it away after package creation.
    - re-verified green on this pass via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_verification.sh` and `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_smoke.sh`.
  - `chummer6-mobile` `993f27a` `feat: surface recap provenance in play shell`
    - workspace-lite and the live play shell now expose recap provenance and audit posture beside publication, lineage, and artifact-shelf follow-through, so the claimed-device return lane says why the recap packet is grounded instead of only where it can be browsed next.
    - verified via `cd /docker/chummercomplete/chummer6-mobile && bash scripts/ai/verify.sh`.
  - `chummer-media-factory` `522429d` `feat: preserve recap provenance in creator packets`
    - `CreatorPublicationPlannerService` now preserves `PublicationSafeProjection` provenance/audit on creator-packet evidence lines, and the recap-brief verify fixture proves that formatting/review no longer strips the recap packet back down to generic creator-publication prose.
    - verified via `cd /docker/fleet/repos/chummer-media-factory && bash scripts/ai/verify.sh`.
  - this recap-provenance slice is preserved as part of the milestone `12` closeout evidence now recorded above.

- 2026-03-30: milestone `12` now has a real durable recap-artifact seam across `chummer6-hub-registry` and `chummer6-hub` instead of synthetic hosted `artifact:` ids.
  - `chummer6-hub-registry` `6acd76ac` `Add replay and recap registry artifact kinds`
    - the owner registry contracts now expose `ReplayPackage` and `RecapPackage`, the registry controller/store now parse and project those kinds directly, and shelf summaries/ownership posture now name replay/recap artifacts explicitly on campaign, creator, owner-only, and retained-history rails instead of flattening them into generic artifact copy.
    - registry verification is green via `cd /docker/chummercomplete/chummer-hub-registry && dotnet run --project Chummer.Hub.Registry.Contracts.Verify/Chummer.Hub.Registry.Contracts.Verify.csproj -c Debug` and `cd /docker/chummercomplete/chummer-hub-registry && dotnet run --project Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj -c Debug`.
  - `chummer.run-services` / `chummer6-hub` `43bc49af` `Persist recap packages as registry artifacts`
    - `CampaignSpineService.RecordAftermathRecapPackage` now registers each hosted recap/downtime package through a persisted `CampaignArtifactRegistryBridge` that reuses the shared `HubArtifactStore` backup contract beside the community-store path, so recap artifacts now survive reload/return/audit as governed registry records instead of one-request synthetic ids.
    - aftermath package projections now keep artifact kind/version/visibility/trust/ruleset plus explicit provenance/audit summaries, recap shelf entries carry that same provenance/audit through server-plane/account/home/public-shelf surfaces, and the personal signed-in artifact shelf now gives dossier projections matching provenance/audit posture instead of ownership-only metadata.
    - hosted verification is green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_verification.sh` and `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_smoke.sh`.
  - this durable recap-artifact seam is preserved as part of the milestone `12` closeout evidence now recorded above.

- 2026-03-30: the retained compatibility tree `/docker/chummer5a` now mirrors milestone `11` workspace portability receipts on the live API/runtime seam instead of stopping at thin import/export payloads.
  - `WorkspaceService`, workspace contracts, API endpoint DTOs, and `HttpChummerClient` now carry governed import/export portability receipts, receipt/package ids, timestamps, compatibility posture, supported exchange modes, and payload-hash provenance in the retained tree too.
  - retained presentation state now keeps the last portable import/export activity visible on the desktop workbench flow, import follow-through preserves the richer notice text, and the retained presenter/client tests now guard the same portable import/export wording and receipt mapping as the owner repos.
  - verified by a clean retained-tree compile via `cd /docker/chummer5a && dotnet build Chummer.Tests/Chummer.Tests.csproj -f net10.0`; retained-tree `dotnet test` execution remains blocked on this Linux image because the generated `Chummer.Tests.runtimeconfig.json` requires `Microsoft.WindowsDesktop.App 10.0.0`.

- 2026-03-30: `chummer-design` now records milestone `11` (portable dossier/campaign federation and external exchange) as complete in both canonical design and the Fleet mirror.
  - Closeout evidence is now green across the owner set: `chummer6-core` import/export receipts keep dossier portability explicit with compatibility notes and provenance; `chummer6-hub` interop/export plus hosted home/account work show campaign portability as a governed ecosystem seam with inspect-only, merge, replace, and format posture; `chummer6-ui` desktop home and shared workbench keep the same portable exchange receipts visible after the action instead of flattening them into backup-style file notices.
  - Verified via `cd /docker/chummercomplete/chummer-core-engine && bash scripts/ai/verify.sh`, `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_verification.sh && bash scripts/ai/run_services_smoke.sh`, and `cd /docker/chummercomplete/chummer6-ui && bash scripts/ai/verify.sh`.

- 2026-03-30: milestone `11` portable exchange is now explicit on the hosted signed-in home/account campaign rails instead of staying trapped in API payloads and desktop-only projections.
  - `chummer.run-services` / `chummer6-hub` `0552ea96` `feat: surface hosted portable exchange`
    - `CampaignWorkspaceServerPlaneService` now emits a first-class `portable_exchange` decision notice with governed inspect-only/merge/replace posture, scope summary, run-pin status, and exchange-format language derived from the shared campaign workspace.
    - signed-in `/home` and `/account/work/workspaces/{id}` now render portable exchange explicitly on the shared campaign card and the “What changed for me” rail instead of burying it under a generic follow-through notice.
    - hosted verification stayed green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_verification.sh` and `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_smoke.sh`.

- 2026-03-30: milestone `11` portable dossier/campaign exchange now behaves like a governed ecosystem seam across hosted interop, desktop home, and the shared workbench follow-through.
  - `chummer.run-services` / `chummer6-hub` `fc7782b7` `feat: harden portable exchange receipts`
    - `InteropExportService` now emits explicit export/import compatibility receipts with format identity, supported exchange formats, inspect-only posture, merge/replace outcome language, and pinned-session guidance instead of treating campaign portability like a backup sidecar.
    - governed replace is now validation-safe: assets are staged first, tampered packages no longer cut over campaign truth, and blocked replace attempts come back with explicit compatibility receipts plus zero mutation count.
    - owner-repo verification is green via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_verification.sh` and `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_smoke.sh`.
  - `chummer6-ui` `12fd4434` `feat: surface portable exchange on desktop home`
    - desktop home now pulls the hosted interop export preview directly, then surfaces portable exchange receipt summary, context, asset scope, supported formats, and watchouts on the same campaign readiness rail as continuity, support, and build-follow-through.
  - `chummer6-ui` `85344edd` `feat: persist portable workbench receipts`
    - the shared workbench now keeps the last portable import/export receipt visible after the action completes, so inspect-only, merge, replace, and compatibility-note guidance survives beyond a one-line toast on both Blazor and Avalonia shells.
    - owner-repo verification is green via `cd /docker/chummercomplete/chummer6-ui && bash scripts/ai/verify.sh`.

- 2026-03-30: milestone `11` portability/exchange receipts are now first-class on the local workspace import/export seam instead of backup-only file notices.
  - `chummer6-core` `a13c4472` `Add workspace portability receipts`
    - `WorkspaceImportResult`, `WorkspaceExportReceipt`, and their API response contracts now carry explicit portability receipts, receipt/package ids, timestamps, compatibility state, next-safe-action language, and payload-hash provenance instead of stopping at file name plus byte count.
    - `WorkspaceService` now emits governed import/export portability receipts directly from the deterministic core path, with section-coverage notes on export and provenance-backed import posture on restore.
    - owner-repo verification is green via `cd /docker/chummercomplete/chummer-core-engine && bash scripts/ai/verify.sh`.
  - `chummer6-ui` `8c361a37` `Surface workspace portability notices`
    - `HttpChummerClient` now maps the richer import/export receipt fields, workspace import now lands with a portability notice instead of a generic success banner, export notices now call out the portable handoff rail, and dialog follow-through no longer stomps the import receipt text.
    - presenter regression coverage now proves the new portable import/export notice copy on the workbench flow.
    - owner-repo verification is green via `cd /docker/chummercomplete/chummer-presentation && bash scripts/ai/verify.sh`.
  - downstream hosted proof stayed green on the same package-plane pass via `cd /docker/chummercomplete/chummer.run-services && bash scripts/ai/run_services_verification.sh && bash scripts/ai/run_services_smoke.sh`.

- 2026-03-30: `chummer6-core` and `chummer6-ui` are back in contract alignment for the milestone-9 rules-lifecycle rail after stale local package/artifact drift.
  - `chummer6-core` `f46d9cdc` `Add rule profile lifecycle stage constants`
    - `RuleProfileRegistryContracts` now publishes explicit `sandbox`, `campaign-approved`, and `published` lifecycle stage constants for rule profiles, so the governed rule-environment rail has one engine-owned vocabulary instead of scattered string literals.
    - owner-repo verification is green again via `cd /docker/chummercomplete/chummer-core-engine && bash scripts/ai/verify.sh`.
  - `chummer6-ui` `407dada2` `Align runtime inspector showcase with current contract`
    - the runtime-inspector showcase/sample constructors now match the current `RuntimeInspectorPromotionProjection` contract instead of carrying a stale required `LifecycleStage` argument that no longer exists in the engine-owned shape.
    - owner-repo verification is green again via `cd /docker/chummercomplete/chummer-presentation && bash scripts/ai/milestones/b8-runtime-inspector-check.sh` and `cd /docker/chummercomplete/chummer-presentation && bash scripts/ai/verify.sh`.
  - Hosted proof was refreshed on the same pass via `cd /docker/chummercomplete/chummer.run-services && bash scripts/ai/run_services_verification.sh && bash scripts/ai/run_services_smoke.sh`.

- 2026-03-30: the design supervisor can now run directly on the EA `core` hard-coder lane instead of being trapped behind the protected local Codex account pool.
  - `scripts/chummer_design_supervisor.py` now supports a `worker_lane` prefix for the worker binary, skips local account rotation when that direct lane is configured, gives the direct lane its own writable Codex home under Fleet state, and defaults away from stray GPT fallback models when the lane owns the model choice.
  - `tests/test_chummer_design_supervisor.py` now verifies the `codexea core exec` command shape and the direct-lane launch path.
  - The local `runtime.env` currently points the supervisor at `/docker/fleet/scripts/codex-shims/codexea` with `CHUMMER_DESIGN_SUPERVISOR_WORKER_LANE=core`, and the live container now shows `model_provider="ea"`, `model="ea-coder-hard"`, and `X-EA-Codex-Profile="core"` on the active worker process for milestone `9`.

- 2026-03-30: Fleet now has a repo-local supervisor OODA monitor for sustained watch/intervention windows.
  - `scripts/ooda_design_supervisor.py` watches `fleet-controller` plus `fleet-design-supervisor`, logs observe/orient cycles under `state/design_supervisor_ooda/`, restarts the supervisor when the loop stalls, and calls `scripts/repair_fleet_credential.sh` for auth-backed source failures on cooldown.
  - The smoke run already exercised the repair path: shared and Archon ChatGPT auth refresh helpers completed successfully, while the stale `OPENAI_API_KEY` repair path stayed explicitly blocked because no alternate working key was available in the scanned env files.

- 2026-03-30: Fleet now supports a first-class `desktop_client` steering profile for the Chummer design supervisor, and the live runtime is pinned to it.
  - `scripts/chummer_design_supervisor.py` now expands named focus profiles into owner/text steering, lets profile steering override the handoff frontier when the operator intentionally redirects the loop, and persists the applied focus profile/owners/text in supervisor status output.
  - `scripts/run_chummer_design_supervisor.sh` and `runtime.env.example` now expose `CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE`, while `docker-compose.yml` now stops blanking the supervisor steering vars so the values from `runtime.env` actually reach the container.
  - The local `runtime.env` currently sets `CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE=desktop_client` with the protected owner pool `tibor.girschele,the.girscheles,archon.megalon`.
  - The profile biases the loop toward desktop-client delivery across `chummer6-ui`, `chummer6-core`, `chummer6-hub`, `chummer6-ui-kit`, `chummer6-hub-registry`, and `chummer6-design`, with text steering for desktop/client/workbench/build/rules/explain/SR4-SR6 flows so the next autonomous slices stay pointed at a shippable Chummer6 desktop client instead of drifting back to broader queue frontage.
  - Verified via `python3 -m pytest tests/test_chummer_design_supervisor.py -q`.
  - The supervisor now fingerprints each credential source and clears saved source backoff automatically when the underlying auth JSON or API key actually changes, so refreshed accounts become eligible again on the next loop pass instead of waiting for the old auth backoff to expire.

- 2026-03-30: Fleet controller routing now allows protected-operator accounts that explicitly opt into `ordinary_burst` to serve `core_booster`.
  - `controller/app.py` now treats a protected operator account with explicit `ordinary_burst` opt-in as an allowed override on `core_booster` instead of rejecting it purely because quartermaster blocks the broader account class on that lane.
  - `tests/test_controller_routing.py` now guards the contract for the `archon.megalon` style opt-in path.
  - Verified via `python3 -m pytest tests/test_controller_routing.py -k "protected_operator_for_ordinary_burst or ordinary_burst_role or core_authority" -q`.

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

- 2026-03-30: `chummer-design` now records milestone `3` (crew/roster operations) and milestone `5` (safehouse/travel prefetch) as complete in both canonical design and the Fleet mirror.
  - Closeout evidence is already executable and green: hosted smoke covers governed roster transfer planning, audited ownership transfer, operator rail continuity, governed prep/travel actions, and claimed-device travel-prefetch receipts; mobile regression checks keep bounded offline use, install-local cache boundaries, and claimed-device return follow-through explicit; Fleet journey gates remain `ready` on the current published evidence.
  - Verified via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_verification.sh && bash scripts/ai/run_services_smoke.sh`, `cd /docker/chummercomplete/chummer6-mobile && bash scripts/ai/verify.sh`, and `python3 /docker/fleet/scripts/materialize_journey_gates.py --out /tmp/JOURNEY_GATES.current.json --status-plane /docker/fleet/.codex-studio/published/STATUS_PLANE.generated.yaml --progress-report /docker/fleet/.codex-studio/published/PROGRESS_REPORT.generated.json --progress-history /docker/fleet/.codex-studio/published/PROGRESS_HISTORY.generated.json --support-packets /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json`.

- 2026-03-30: `chummer-design` now records milestone `4` (NPC/opposition packets and GM prep library) as complete, which closes W1 in both canonical design and the Fleet mirror.
  - Closeout evidence is now green across the owner set: `chummer6-hub` search/launch smoke keeps governed opposition packets searchable and campaign-bindable without local shadow prep notes, `chummer6-ui` NPC Persona Studio remains contract-driven, `chummer6-core` NPC pack compatibility matrices preserve prepared opposition truth, and `chummer6-media-factory` runtime verification stays green on the governed creator/packet planning seam.
  - Verified via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_smoke.sh`, `cd /docker/chummercomplete/chummer6-ui && bash scripts/ai/milestones/b11-npc-persona-studio-check.sh`, `cd /docker/fleet/repos/chummer-media-factory && dotnet run --project Chummer.Media.Factory.Runtime.Verify/Chummer.Media.Factory.Runtime.Verify.csproj`, and `cd /docker/chummercomplete/chummer6-core && bash scripts/ai/test_core_engine.sh`.

- 2026-03-30: `chummer-design` now records milestone `8` (Rules Navigator v2) as complete in both canonical design and the Fleet mirror.
  - Closeout evidence is now green across the owner set: `chummer6-hub` campaign spine, support assistant, account work, and signed-in public landing all reuse the same grounded rules projection with before/after diffs and support-reuse hints; `chummer6-ui` Rules Navigator panel plus desktop home carry the same provenance and diff posture; `chummer6-core` runtime-lock diff and runtime-inspector seams keep the underlying rule-environment change truth deterministic.
  - Verified via `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_smoke.sh`, `cd /docker/chummercomplete/chummer6-ui && bash scripts/ai/verify.sh`, and `cd /docker/chummercomplete/chummer-core-engine && bash scripts/ai/verify.sh`.

- 2026-03-30: `chummer-design` now records milestone `10` (Explain receipts everywhere) as complete in both canonical design and the Fleet mirror.
  - Closeout evidence is now green across the owner set: `chummer6-core` deterministic build/runtime/migration receipt seams stay engine-owned; `chummer6-ui` desktop home plus runtime-inspector and build-path surfaces render compatibility, migration, rules, and support receipts from shared projections; `chummer6-hub` signed-in home/account/support/downloads keep release-progress, support-closure, migration, and fix-eligibility receipts visible from the same campaign/support truth; `chummer6-mobile` workspace-lite keeps support closure and rule-environment receipt posture on the bounded return lane.
  - Verified via `cd /docker/chummercomplete/chummer-core-engine && bash scripts/ai/test_core_engine.sh`, `cd /docker/chummercomplete/chummer6-ui && bash scripts/ai/verify.sh`, `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_verification.sh && bash scripts/ai/run_services_smoke.sh`, and `cd /docker/chummercomplete/chummer6-mobile && bash scripts/ai/verify.sh`.

- 2026-03-30: `chummer-design` now records milestone `9` (Rule-environment studio and governed promotion) as complete in both canonical design and the Fleet mirror.
  - Closeout evidence is now green across the owner set: `chummer6-core` runtime inspector now projects explicit sandbox -> campaign-approved -> published lifecycle stages with rollback and lineage posture; `chummer6-ui` desktop runtime inspector and rules navigator both render the same lifecycle and promotion target directly; `chummer6-hub` account work, signed-in home, restore summaries, and workspace rule-health surfaces now carry the same governed studio language instead of raw approval-state shorthand.
  - Verified via `cd /docker/chummercomplete/chummer-core-engine && bash scripts/ai/verify.sh`, `cd /docker/chummercomplete/chummer6-ui && bash scripts/ai/verify.sh`, and `cd /docker/chummercomplete/chummer6-hub && bash scripts/ai/run_services_verification.sh && bash scripts/ai/run_services_smoke.sh`.

- The active frontier from `chummer-design` is now W3 milestones `11` through `14` after the W2 rules-lifecycle closeout.
- Fleet now has a repo-local design-completion supervisor:
  - `scripts/chummer_design_supervisor.py` derives the active frontier directly from the canonical registry, roadmap, and `NEXT_SESSION_HANDOFF.md`, writes durable run state under `state/chummer_design_supervisor/`, and launches bounded `codex exec` worker runs across `/docker/fleet`, `/docker/chummercomplete`, `/docker/fleet/repos`, `/docker/chummer5a`, and `/docker/EA`.
  - `scripts/run_chummer_design_supervisor.sh` is the launch helper and now expands env-driven steering/account flags (`CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_OWNER_IDS`, `CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_ALIASES`, `CHUMMER_DESIGN_SUPERVISOR_FOCUS_OWNER`, `CHUMMER_DESIGN_SUPERVISOR_FOCUS_TEXT`) before it starts the loop.
  - `docker-compose.yml` now includes `fleet-design-supervisor`, so a normal Fleet compose boot owns restart-on-reboot for the loop instead of relying on a shell or tmux session.
  - `python3 scripts/chummer_design_supervisor.py trace --state-root state/chummer_design_supervisor --limit 20` now renders the recent OODA/operator history directly from Fleet state instead of forcing raw JSONL inspection.
  - Retryable worker-model failures now surface a compact failure hint in `status`/`trace`, and the supervisor automatically retries fallback models (`--fallback-worker-model`, default fallback `gpt-5.4`) when the current model returns a quota/support-style error.
  - The supervisor now also rotates across protected operator account pools from `config/accounts.yaml` by default, including `tibor.girschele`, `the.girscheles`, and `archon.megalon`, with source-aware backoff for usage-limit/auth/rate-limit failures.
  - Steering is now a first-class seam: use `--focus-owner chummer6-ui` or `CHUMMER_DESIGN_SUPERVISOR_FOCUS_OWNER=chummer6-ui` to bias the frontier toward finishing the desktop client first without dropping the rest of the open milestone set.
  - The current dry-run derivation should now skip completed W2 work and re-derive directly into milestones `11` through `14`.
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

Do not reopen the already-landed W2 registry, milestone `11` portability, or signed-in-home slices unless a new regression appears.

The next useful re-derivation should come from `chummer-design` and continue W3 from the remaining unfinished seams:

- `chummer6-hub` / `chummer6-mobile` / `chummer6-media-factory` / `chummer6-hub-registry`
  - continue milestone `12` by wiring replay package issuance plus registry/publication search-preview carry-through onto the durable recap-artifact seam that now already reaches hosted shelf projection, the mobile return shell, and media-factory creator packets
- `chummer6-media-factory` / `chummer6-hub` / `chummer6-hub-registry` / `chummer6-design`
  - start milestone `13` by turning creator publication into discovery, lineage, moderation, and trust-ranked truth instead of one-way output shelves
- `chummer-design`
  - keep canon and mirrors aligned as milestone `12` and `13` evidence lands

The main rule for the next session is unchanged: re-derive from `chummer-design`, not from the last clean repo boundary.
