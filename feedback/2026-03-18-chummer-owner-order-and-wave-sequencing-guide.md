I’m assigning owner roles by repo responsibility rather than person-name, because the canonical program state names ownership by repo and milestone, not by individual maintainer. The release-critical blockers still called out in canon are `A0`, `A1`, `A2`, `C1`, and `D1`, and the red blocker themes are still design canon, package canon, and session-semantic duplication. ([GitHub][1])

## Program order I would enforce

**P0 is truth convergence and seam closure. P1 is boundary purification and promotion hygiene. P2 is expansion and hardening.** I would not let the org treat any repo as “done” until design’s four-state taxonomy exists and is wired through Fleet: `repo-local complete`, `package-canon`, `boundary pure`, `public promoted`. That work is already queued as WL-D019, WL-D020, and WL-D021 in `chummer6-design`. ([GitHub][2])

My sequencing would be:

1. **Design + Fleet + Chummer6 first.** Right now design says the guide must source horizon existence and ordering from `HORIZON_REGISTRY.yaml`, but `Chummer6` still carries a much larger hand-curated Horizons set and Fleet’s `guide.yaml` still hardcodes those older pages. Until that is fixed, every public-facing statement about the future can drift again. ([GitHub][3])

2. **Core + Hub + Mobile second.** `A1`, `A2`, and `D1` are still open, and they are the contract/semantic blockers that make replay, transport, and reducer truth vulnerable to duplication. ([GitHub][1])

3. **Hub + Hub-registry + Media-factory third.** `C0` and `C1` are still open because owner transfer is not yet complete; package existence is not the same thing as runtime authority transfer. ([GitHub][1])

4. **UI + UI-kit fourth.** The feature lanes are ahead of the boundary lanes; the next win is deleting or quarantining what should not be in `chummer6-ui` and making `Chummer.Ui.Kit` impossible to bypass. ([GitHub][4])

5. **EA and broader platform hardening after that.** EA is already a real runtime, but Fleet still lists runtime-profile, provider-registry, typed metadata, and docs/runtime sync debt. Those matter, but they should not preempt the Chummer release blockers. ([GitHub][5])

One global rule for every dev: **fix queue truth before feature truth.** Right now core, UI, and hub all still have worklist/summary mismatches or “queue empty but queued work exists” style drift, and design already has WL-D020/WL-D021 queued to stop that from happening. Every repo should have one truthful queue summary, one readiness state, and one acceptance ledger. ([GitHub][6])

## Changeguide by repo

### Chummer6 — owner role: public guide lead

**P0:** stop hand-curating Horizons. Regenerate `HORIZONS/` from `HORIZON_REGISTRY.yaml` plus `PUBLIC_GUIDE_EXPORT_MANIFEST.yaml`, and remove any public page that is not currently enabled in canonical design. **Acceptance:** the public Horizons index contains only the currently enabled horizons from the registry, and Fleet verify is no longer a hardcoded list of legacy pages like `ghostwire`, `rule-xray`, `heat-web`, `run-passport`, `threadcutter`, and `mirrorshard`. **P1:** align public status tone with actual promotion state; keep “preview” as the governing readiness label until the deployment and release shelves say otherwise. **P2:** stamp every guide publish with the registry/manifest source hash so drift becomes obvious on the page itself. ([GitHub][7])

### chummer6-design — owner role: design lead / contract steward

**P0:** land WL-D019, WL-D020, and WL-D021. That means Fleet must compile from design canon, the four-state readiness taxonomy must be operational, and active blockers must be decomposed into explicit, milestone-linked rows with owner mapping. **Acceptance:** Fleet config, repo mirrors, blocker ledgers, and program summaries all show the same state; no repo can self-promote from “repo-local complete” to “boundary pure” or “public promoted” without explicit evidence. **P1:** only then advance `A0`, `H0`, and `H1`; the files already exist, but design should not mark them closed until the guide and Fleet are actually obeying them. **P2:** keep WL-D016/17/18 as recurring maintenance lanes, not as a substitute for real blocker closure. ([GitHub][2])

### chummer6-core — owner role: engine lead

**P0:** do the physical cleanup before any more semantic victory laps. WL-100 and WL-101 are the real work: quarantine legacy app/plugin/browser cargo and close the namespace ambiguity so `Chummer.Engine.Contracts` is the only canonical engine/shared contract surface. **Acceptance:** CI rejects legacy contract roots as active ownership, the repo tree no longer overstates browser/app/plugin ownership, and `A1` can be evidenced without hand-waving. **P1:** then close WL-098/WL-099 so the queue overlay and milestone mapping reflect the cleaned boundary instead of coarse follow-through prompts. **P2:** move on to `D0` and `F1` hardening only after `A1` is physically visible. ([GitHub][8])

### chummer6-ui — owner role: workbench lead

**P0:** stop treating feature completion as the problem. WL-201 is the real blocker: move remaining legacy desktop/helper/tooling roots out of the primary repo body or quarantine them as explicit compatibility cargo, and land WL-200 so `Chummer.Ui.Kit` shell/accessibility primitives cannot be recopied locally. **Acceptance:** `B2` can be evidenced by the tree itself, not just by the README; the workbench/browser/desktop repo visibly looks like workbench/browser/desktop ownership, and CI fails if B1 primitives are reintroduced locally. **P1:** publish one clear binary-promotion rule so installer-capable delivery has a single source of truth. **P2:** finish F0-quality work only after boundary purity is no longer in dispute. ([GitHub][4])

### chummer6-mobile — owner role: play-shell lead

**P0:** close WL-024 and treat it as a release-critical seam, not a cleanup chore. The mobile shell is in good shape locally; the remaining work is to prove that replay, resume, and rejoin consume canonical session semantics from shared contracts and do not invent a second semantic family in adapters. **Acceptance:** end-to-end checks in `scripts/ai/verify.sh` prove package-only consumption of `Chummer.Play.Contracts`, replay/resume remain transport-safe, and no local semantic expansion exists in role-shell adapters. **P1:** keep hardening on cross-device continuity, replay trust, and PWA fit. **P2:** retire the last compatibility alias once the audit history is preserved. ([GitHub][9])

### chummer6-hub — owner role: orchestrator lead

**P0:** land WL-231 and WL-232. That means moving any repo-local `Chummer.Media.Contracts` ownership into explicit compatibility-wrapper territory only, and publishing route/contracts proof that `Play` and `Run` seams are transport wrappers over canonical semantics rather than second semantic owners. **Acceptance:** `HOSTED_BOUNDARY.md` no longer reads like hub is the long-term owner of media and registry semantics, `/api/play/*` and `Chummer.Run.Contracts` are documented as transport/composition seams, and hub no longer looks like the hidden super-repo. **P1:** continue the C2 shrink until registry persistence and media execution are visibly elsewhere. **P2:** only after that should hub expand docs/feedback/operator or assistant-plane work. ([GitHub][10])

### chummer6-ui-kit — owner role: design-system lead

**P0:** make downstream discipline real. The ui-kit repo already has the token/shell/accessibility B1 slice internally complete; now UI and mobile must delete local copies and add rg/CI guards that fail on reintroduction. **Acceptance:** the consumer repos provide commit/path evidence that the relevant shell/accessibility primitives are package-only, and CI in presentation/play fails if those classes reappear as source copies. **P1:** then expand into U4/U5 dense-data and Chummer-specific reusable patterns. **P2:** after consumer adoption is closed, build out the catalog, visual regression, and release-discipline lane. ([GitHub][11])

### chummer6-hub-registry — owner role: registry lead

**P0:** finish authority transfer, not just contract extraction. The open work is exactly right: publication metadata, review outcomes, compatibility projections, and registry-backed read-model writes must move so hosted services become contract consumers only. **Acceptance:** immutable artifact metadata, publication state, review outcomes, install/compatibility projections, and runtime-bundle head state are written and projected here, while hub only consumes `Chummer.Hub.Registry.Contracts`; docs should also stop teaching old `run-services`/“Presentation” topology as the live world. **P1:** then deepen artifact-domain and search/discovery/review features. **P2:** federation or org-channel work only after `C0` is visibly closed. ([GitHub][12])

### chummer6-media-factory — owner role: media lead

**P0:** turn the repo from a correct contract/evidence plant into a visibly running media service. The contract plane is real, the seam expectations are documented, and the asset-kernel/backlog evidence exists; the missing proof is live render cutover depth. **Acceptance:** there is a real runtime surface beyond the contract package, provider adapters are switchable and adapter-private, every media job emits manifests/receipts/provenance, and hub consumes the media seam instead of effectively owning render execution. **P1:** close `C1c` with the document/preview/route/video/archive adapters and DR/storage behavior. **P2:** only then push toward stable document/portrait/video product planes. ([GitHub][13])

### fleet — owner role: fleet compiler lead

**P0:** implement WL-D019 for real. Fleet should stop being a second architecture brain and become a compiler of `chummer6-design` canon. Start with the guide: `guide.yaml` must stop hardcoding old horizon pages and instead derive its expectations from the design export manifest/registry. Then refresh `program_milestones.yaml` so it no longer carries stale uncovered-scope text that contradicts current mobile, ui-kit, hub-registry, and media-factory reality. **Acceptance:** no hardcoded horizon catalog in Fleet config, no stale uncovered-scope lines that design has already superseded, and every published repo/deployment status is generated or validated from design canon plus repo evidence. **P1:** once that exists, wire in WL-D020’s readiness taxonomy so protected-preview, repo-local complete, package-canon, and public-promoted stop colliding. **P2:** keep compile-manifest and parity evidence mandatory on every publish. ([GitHub][14])

### executive-assistant — owner role: runtime lead

**P0:** finish the runtime-governance core: authoritative startup/runtime profile resolution, provider registry as runtime truth, and typed workflow/skill metadata instead of loose JSON drift. EA already looks like a real platform and the Chummer-specific skill catalog already consumes `design_scope` and `public_status`; now the governance layer needs to catch up. **Acceptance:** boot selects one authoritative runtime mode, provider availability/capability routing is first-class runtime data, typed read records cover workflow/skill/provider state end to end, and Chummer skills stay subordinate to canonical design/public-status inputs. **P1:** then complete execution/read-model boundary hardening and provider-receipt discipline. **P2:** finish docs/env/deployment sync so the runtime surface matches the routed provider surface exactly. ([GitHub][5])

## The order I would actually run next week

**Wave 1 (must happen first):** `chummer6-design` WL-D019/20/21, `Chummer6` horizon regeneration, Fleet guide verification rewrite. This closes the biggest truth-drift loop immediately. ([GitHub][2])

**Wave 2:** `chummer6-core` WL-100/101, `chummer6-hub` WL-231/232, `chummer6-mobile` WL-024. This is the shortest path to real progress on `A1`, `A2`, and `D1`. ([GitHub][6])

**Wave 3:** `chummer6-hub-registry` authority transfer and `chummer6-media-factory` runtime cutover slices, with hub shrinking in lockstep. This is how you clear `C0` and `C1` instead of just talking about them. ([GitHub][15])

**Wave 4:** `chummer6-ui-kit` consumer enforcement plus `chummer6-ui` WL-200/201. This is the right moment to close B1/B2 honestly. ([GitHub][16])

**Wave 5:** EA governance, then broader quality/release promotion. By then the public story, package story, and runtime story should all be saying the same thing. ([GitHub][17])

The blunt version: **Design must become the compiler source, Fleet must stop improvising, the guide must stop owning a private future catalog, core/hub/mobile must settle contract and session truth, registry/media must become real owners instead of just real repos, and UI/UI-kit must make the split visible in the tree.** That is the shortest path from “coherent architecture” to “credible program.” ([GitHub][3])

[1]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-design/main/products/chummer/PROGRAM_MILESTONES.yaml "raw.githubusercontent.com"
[2]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-design/main/WORKLIST.md "raw.githubusercontent.com"
[3]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-design/main/products/chummer/PUBLIC_GUIDE_POLICY.md "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-design/main/products/chummer/projects/ui.md "raw.githubusercontent.com"
[5]: https://raw.githubusercontent.com/ArchonMegalon/executive-assistant/main/README.md "raw.githubusercontent.com"
[6]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-core/main/WORKLIST.md "raw.githubusercontent.com"
[7]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-design/main/products/chummer/projects/guide.md "raw.githubusercontent.com"
[8]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-design/main/products/chummer/projects/core.md "raw.githubusercontent.com"
[9]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-design/main/products/chummer/projects/mobile.md "raw.githubusercontent.com"
[10]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-design/main/products/chummer/projects/hub.md "raw.githubusercontent.com"
[11]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-design/main/products/chummer/projects/ui-kit.md "raw.githubusercontent.com"
[12]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-design/main/products/chummer/projects/hub-registry.md "raw.githubusercontent.com"
[13]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-design/main/products/chummer/projects/media-factory.md "raw.githubusercontent.com"
[14]: https://raw.githubusercontent.com/ArchonMegalon/fleet/main/README.md "raw.githubusercontent.com"
[15]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-hub-registry/main/WORKLIST.md "raw.githubusercontent.com"
[16]: https://raw.githubusercontent.com/ArchonMegalon/chummer6-ui-kit/main/WORKLIST.md "raw.githubusercontent.com"
[17]: https://raw.githubusercontent.com/ArchonMegalon/fleet/main/config/program_milestones.yaml "raw.githubusercontent.com"
