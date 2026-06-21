# Chummer ADR Index

Approved architecture decisions for cross-repo Chummer design live here.

## Accepted
- [ADR-0001](ADR-0001-contract-plane-canon.md): Contract-plane canon is package-owned and design-first.
- [ADR-0002](ADR-0002-play-split-ownership.md): `chummer6-mobile` owns the play shell and depends only on approved shared packages.
- [ADR-0003](ADR-0003-ui-kit-split.md): `chummer6-ui-kit` is the package-only shared UI boundary.
- [ADR-0004](ADR-0004-hub-registry-split.md): `chummer6-hub-registry` owns registry and publication state after extraction from run-services.
- [ADR-0005](ADR-0005-public-surface-design-first.md): Public landing and guide meaning are design-first, with `chummer.run` and `Chummer6` intentionally split.
- [ADR-0006](ADR-0006-participation-and-sponsored-execution-split.md): Hub owns participation and sponsor-session truth while Fleet owns sponsored execution lanes and signed contribution receipts.
- [ADR-0007](ADR-0007-identity-and-companion-channel-linking.md): Identity, linked-channel policy, and companion-channel ownership stay in Hub, with EA remaining the orchestrator brain behind governed channels.
- [ADR-0008](ADR-0008-release-authority-split.md): Release authority stays split across core, UI, Fleet, hub-registry, Hub, and Media Factory.
- [ADR-0009](ADR-0009-external-tools-plane.md): External tools remain adapter-bound helper planes and never become canonical Chummer truth.
- [ADR-0010](ADR-0010-desktop-auto-update-plane.md): Desktop auto-update is registry-backed, UI-applied, and atomic in its first public wave.
- [ADR-0011](ADR-0011-no-personalized-binaries-claimable-installs.md): Chummer uses claimable installs and account-aware linkage instead of per-user personalized binaries.
- [ADR-0012](ADR-0012-product-governor-and-feedback-loop.md): Whole-product pulse and feedback routing are first-class canon rather than scattered operator instinct.
- [ADR-0013](ADR-0013-campaign-and-control-middle-plane.md): Campaign continuity and product control are first-class middle planes, initially bounded inside Hub rather than left implicit across other repos.
- [ADR-0014](ADR-0014-interop-and-portability-plane.md): Interop and portability are explicit product promises with named owner-package seams instead of compatibility folklore.
- [ADR-0015](ADR-0015-drug-system-semantics-and-application.md): Drug systems are deterministic, ruleset-pluggable, and receipt-backed via core contracts.
- [ADR-0016](ADR-0016-structured-presenter-video-lane.md): Structured presenter video is a bounded media lane behind Chummer-owned media-factory adapters rather than direct product truth.
- [ADR-0017](ADR-0017-first-party-companion-runtime-and-bounded-voice-mode.md): The in-client companion stays first-party, trigger-bound, and explicitly opt-in for voice, while vendor media and public concierge lanes remain downstream helpers.
- [ADR-0018](ADR-0018-world-state-and-mission-market-layer.md): World-state and mission-market layer remains a future capability above the campaign spine; campaign and control truth stay separate from shared-world effects.
- [ADR-0019](ADR-0019-productlift-katteb-public-signal-and-guide-optimization.md): ProductLift and Katteb become bounded public signal and public-content projection lanes, not product truth.
