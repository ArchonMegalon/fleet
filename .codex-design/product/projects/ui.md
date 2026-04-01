# UI implementation scope

## Mission

`chummer6-ui` owns the workbench, browser, and desktop user experience for Chummer6.
It is the repo for builders, inspectors, compare views, explain UX, moderation/admin surfaces, installable desktop delivery, desktop self-update behavior, and in-app bug/feedback/crash entry points.

## Owns

* workbench/browser/desktop UX
* builders, inspectors, and compare flows
* explain and audit-facing UX on the workbench side
* rule-environment selection, inspection, and activation UX
* preset and amend-package preview, diff, and rollback UX
* grouped quality, active-effect, and conditional-modifier organization surfaces
* source-linked tooltips and detail drawers for legality, acquisition, and explain traces
* transaction-safe bundle and PACK preview/apply/cancel UX
* calendar-backed training, downtime, and timed-effect presentation
* moderation and admin surfaces that stay outside the live play shell
* desktop packaging, installer delivery, and workbench-side release polish
* updater integration inside desktop heads
* local install/channel state for desktop clients
* staged apply helpers and relaunch flow
* local crash interception where the client can catch it
* redacted diagnostics bundle creation
* offline spool and retry for support payloads
* next-launch crash recovery UX
* in-app feedback and structured bug-report entry points
* platform-specific packaging adapters that emit machine update payloads
* Windows `.exe`, macOS `.dmg`, and Linux `.deb` installer targets for the desktop release bundle
* platform-specific startup-smoke fixtures that prove each built desktop head can launch
* release-bundle emission for desktop artifacts
* automatic post-build publication of the latest successful desktop bundle into configured self-hosted downloads targets
* the flagship desktop delivery cut with `Chummer.Avalonia` as the primary desktop head and `Chummer.Blazor.Desktop` as the bounded compatibility fallback
* runtime language selection, fallback behavior, and localization-safe desktop release gates for the shipping locale set

## Must not own

* the dedicated play/mobile shell
* offline session-ledger authority
* engine/runtime mechanics truth
* hosted orchestration or provider-secret ownership
* canonical channel or update-feed truth
* rollout or revoke truth for promoted desktop heads
* hosted support-ticket truth
* knowledge-base truth
* support-assistant orchestration
* source-copied shared UI primitives that belong in `Chummer.Ui.Kit`
* archive-style retention of superseded public download bundles

## Package boundary

`chummer6-ui` consumes shared packages. It does not recreate them locally.

Primary consumption boundary:

* `Chummer.Engine.Contracts`
* `Chummer.Ui.Kit`
* `Chummer.Hub.Registry.Contracts` for published desktop release-head and update-feed DTOs

## Restore rule

`chummer6-ui` must restore those shared packages through:

* the canonical local/CI package feed
* or an explicit generated compatibility tree for legacy consumers

Workers must not have to guess whether missing restore is caused by a feed problem or a missing compatibility tree.

## Desktop update rule

The updater backend is not canonical. The ownership split is.

`chummer6-ui` may wrap a third-party updater backend or use a custom helper, but it must still own:

* check/download/stage/apply/relaunch behavior
* local rollback-window state
* per-head startup hooks
* update settings/about UX

It must not invent a second promoted-channel vocabulary or bypass registry-published rollout and revoke truth.

## Support rule

`chummer6-ui` must ship the first support plane as native product UX:

* crash recovery and private crash-report entry
* structured bug reporting
* lightweight feedback

It must not make a chat assistant the first support feature, and it must not require another AppSumo LTD for the core crash path.

## Boundary truth

Feature completion inside this repo was not enough to close the split milestone.
`B2` is now treated as complete because the repo body matches the stated boundary closely enough for release:

* legacy/helper/tooling roots stop dominating the tree
* shared visual chrome migrates into `chummer6-ui-kit`
* play-shell ownership remains fully outside this repo
* installer/release work stays workbench-scoped instead of reabsorbing unrelated ownership

Desktop auto-update is additive evolution after that boundary closure. It must not be implemented by letting desktop concerns leak back into Hub, Fleet, or Core.

## Current reality

The product direction and the release bar are now aligned.
Retained legacy roots are compatibility cargo, not hidden ownership claims.

That means:

* feature maturity and boundary purity now align closely enough to close both `B2` and the workbench share of `E0`
* shared visual chrome is package-owned and regression-guarded
* workbench release evidence is explicit in `docs/WORKBENCH_RELEASE_SIGNOFF.md`
* any retained legacy roots must stay explicitly documented as compatibility cargo
* the first desktop updater wave should ship atomic full-head replacement before delta or runtime-only evolution

The current flagship UX bar also assumes:

* cancel-safe multistep editing
* receipt-backed conditional toggles instead of silent always-on bonuses
* grouped inspection for qualities, gear, and active effects
* in-game timeline visibility where calendar or training state matters
* authored SR4, SR5, and SR6 UX where edition differences materially change how builders reason about the character
* explicit rule-environment badges, package drift warnings, and restore-safe "missing pack" recovery paths
* dense-data comfort and visual polish that make the desktop client feel premium under heavy expert use rather than merely feature-complete
