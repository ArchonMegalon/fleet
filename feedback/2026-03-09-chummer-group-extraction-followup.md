# Chummer Group Follow-up: package plane and next split audit

Date: 2026-03-09

## Summary

- `chummer-play` is the correct split, but it is still an extraction in progress rather than a completed separation.
- The contract plane is still not real: the play repo README expects `Chummer.Contracts`, while `Directory.Build.props` defaults to `Chummer.Engine.Contracts`, and there is still no public `Chummer.Play.Contracts` package/project.
- `chummer-presentation` still owns session/mobile shell surfaces (`Chummer.Session.Web`, `Chummer.Coach.Web`) even though `chummer-play` now exists.
- `chummer-core-engine` and `chummer.run-services` still carry broad authority clutter and legacy helper/tooling surfaces at the repo root.

## Group-level recommendations

1. Make the package plane real now.
   - Canonicalize engine/shared package naming.
   - Publish a real `Chummer.Play.Contracts`.
   - Treat `Chummer.Ui.Kit` as the next shared UI package boundary.

2. Finish the play extraction.
   - Move session/mobile shell ownership out of Presentation.
   - Replace scaffolded play bootstrap, API client, and event-log storage with real play runtime seams.

3. Prepare the next clean repo splits only after the package seams exist.
   - `chummer-ui-kit`
   - `chummer-hub-registry`
   - `chummer-media-factory`

## Scoped actions

### core
- Remove presentation/run-service/browser/legacy clutter from the core authority boundary.

### ui
- Stop owning `Chummer.Session.Web` and `Chummer.Coach.Web`.
- Keep workbench and UI-kit ownership only.

### hub
- Publish `Chummer.Play.Contracts` and dedicated `/api/play/*` seams.
- Keep registry/media/relay surfaces cleanly split from legacy clutter.

### mobile
- Align package ids with the canonical contract plane.
- Replace scaffold-stage bootstrap/session client/offline ledger code.
