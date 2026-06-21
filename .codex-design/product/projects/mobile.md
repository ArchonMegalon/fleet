# Mobile implementation scope

## Mission

`chummer6-mobile` owns the dedicated player/GM/session shell for Chummer6:
local-first play, reconnect/replay behavior, mobile/tablet UX, and installable PWA hardening.

## Owns

* player shell and GM shell for live play
* local-first session ledger handling on the client side
* reconnect, replay, resume, and observer continuity on the play shell side
* offline/media caching for play use
* dedicated `/api/play/*` route consumption and play-shell integration
* installable PWA hardening for mobile/tablet play

## Must not own

* workbench/browser/desktop builder UX
* engine/rules evaluation truth
* registry or publication moderation UX
* hosted orchestration ownership
* copied shared contracts or copied shared UI primitives

## Package boundary

`chummer6-mobile` must consume canonical shared packages only:

* `Chummer.Engine.Contracts`
* `Chummer.Play.Contracts`
* `Chummer.Campaign.Contracts` for campaign continuity projections
* `Chummer.World.Contracts` for world-state and mission-market projections
* `Chummer.Ui.Kit`

## Boundary truth

The mobile boundary is healthy when the live shell can trust replay/resume without re-owning engine or workbench concerns.

Current exit criteria remain practical, not decorative:

* WL-005 class local-first seams must be boringly trustworthy
* observer and cross-device continuity must stay in the play-shell boundary
* package-only discipline must remain strict
* old `chummer6-mobile` naming must disappear from the live repo identity

## Current reality

This split is materially healthy enough to close `B0`, `A2`, `D1`, and `E1`.
Remaining work is future capability depth and cross-head polish, not whether the play shell, its replay/resume guarantees, or its package seams are real.

## Flagship-grade bar

`chummer6-mobile` is not flagship grade until:

* reconnect, replay, and resume feel boring under real session stress
* player and GM flows read as authored live-play experiences rather than downsized workbench screens
* offline and degraded-network posture is visible enough that the table knows what is safe to trust
