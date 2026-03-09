# Project Chummer — Change Plan and Milestones for Dev

Date: 2026-03-09
Audience: repo owners and Codex worker agents

## Executive summary

The Chummer repo graph is still half-extracted.

What is real:

- `chummer-play` exists and owns the dedicated play/mobile seam
- `chummer.run-services` already has strong seams for Registry and Media work
- `Chummer.Run.Contracts` is much more decomposed than before

What still needs action:

- normalize on `Chummer.Engine.Contracts`
- publish a real `Chummer.Play.Contracts`
- finish moving session/mobile shell ownership out of Presentation
- purge cross-boundary contract projects and legacy clutter from Core
- canonicalize engine mutation versus play transport session DTOs
- split the next clean repos in order: `chummer-ui-kit`, `chummer-hub-registry`, then `chummer-media-factory`

## Milestone order

1. M0 — contract canon and design-doc correction
2. M1 — finish `chummer-play` extraction
3. M2 — create `chummer-ui-kit`
4. M3 — create `chummer-hub-registry`
5. M4 — create `chummer-media-factory`
6. M5 — shrink `chummer.run-services` to the orchestrator shell
7. M6 — purify `chummer-core-engine`
8. M7 — documentation and release hardening

## Repo direction

- `core`: remove `Chummer.Presentation.Contracts`, `Chummer.RunServices.Contracts`, browser infrastructure, and legacy utility clutter after package cutover.
- `ui`: keep workbench/browser/desktop ownership, remove dedicated play shell ownership, and consume `Chummer.Ui.Kit`.
- `hub`: publish `Chummer.Play.Contracts`, split render-only media contracts from narrative-generation DTOs, and prepare registry/media extractions.
- `mobile`: replace scaffolded browser session/offline seams, consume package-only dependencies, and own the dedicated play shell fully.

## Immediate queue focus

- update `chummer-play` docs and package names to `Chummer.Engine.Contracts`
- define visible `Chummer.Play.Contracts` ownership in hosted services
- write the next Presentation design doc without mobile/session-shell ownership
- seed `chummer-ui-kit`
- seed `chummer-hub-registry`
- split media contracts before `chummer-media-factory`
- quarantine cross-boundary source projects out of Core
