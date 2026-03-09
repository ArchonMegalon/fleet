# Project Chummer — Repo Split Guide

Date: 2026-03-09
Audience: maintainers and Codex worker agents

## Summary

The next Chummer wave is:

1. Stabilize the contract plane.
2. Finish `chummer-play`.
3. Create `chummer-ui-kit`.
4. Create `chummer-hub-registry`.
5. Split media contracts cleanly, then create `chummer-media-factory`.

The key rule is that extraction follows contract canon, not the other way around.

## Preconditions

Do not treat the next repo splits as clean until all of these are true:

- canonical engine package name is `Chummer.Engine.Contracts`
- `Chummer.Play.Contracts` exists as a real source project and package
- the session model is canonicalized into engine mutation plus play transport
- Presentation no longer claims mobile/session shell ownership in design docs

## Split Order

1. `chummer-ui-kit`
2. `chummer-hub-registry`
3. `chummer-media-factory`

## Repo-scoped direction

- `core`: purge `Chummer.Presentation.Contracts`, `Chummer.RunServices.Contracts`, browser infrastructure, and legacy utility clutter after package cutover.
- `ui`: keep workbench/browser/desktop ownership, move dedicated play shell ownership out, and consume `Chummer.Ui.Kit` as a package-only seam.
- `hub`: publish `Chummer.Play.Contracts`, define the engine-mutation plus play-transport session model, and split registry/media seams by domain.
- `mobile`: finish the extraction, replace scaffolded browser session/offline seams, and consume `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Ui.Kit` only.

## Immediate tasks

- Canonicalize package naming on `Chummer.Engine.Contracts`.
- Publish a real `Chummer.Play.Contracts`.
- Finish removing play/mobile shell ownership from Presentation docs and repo layout.
- Seed `chummer-ui-kit` as the next low-risk package-only repo.
- Stage `chummer-hub-registry` behind the stabilized contract plane.
- Split media contracts into render-only versus narrative-generation families before bootstrapping `chummer-media-factory`.
