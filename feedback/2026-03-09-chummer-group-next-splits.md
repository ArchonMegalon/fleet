# Chummer Group Next Splits Audit

Date: 2026-03-09

## Summary

- `chummer-play` was the correct first split, but it is still an extraction in progress rather than a finished separation.
- The main blocker is still the contract plane: package naming drifts, `Chummer.Play.Contracts` is not public yet, and package-only boundaries are not fully real.
- `chummer-presentation` still owns session/mobile shell surfaces that now belong with `chummer-play`.
- `chummer-core-engine` and `chummer.run-services` still carry broad mixed-authority and legacy/tooling clutter.

## Priority Order

1. Make the contract plane real.
   - Standardize on `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Run.Contracts`.
   - Remove `Chummer.Presentation.Contracts` and `Chummer.RunServices.Contracts` source trees from core.

2. Split `chummer-ui-kit`.
   - Move design tokens, layout primitives, accessibility primitives, shared cards/lists/forms, offline banners, stale-state badges, approval chips, iconography, and motion policy into a package-only repo.
   - Keep UI kit free of domain DTOs, HTTP clients, local storage, and rules math.

3. Split `chummer-hub-registry`.
   - Isolate publication, immutable artifacts, runtime bundle catalog, NPC vault, build-idea library, reviews, moderation, and install history.

4. Split `chummer-media-factory`.
   - Isolate portrait jobs, dossier/news rendering, thumbnails, route-video jobs, asset manifests, approval states, and lifecycle policy.

5. Later, split legacy/interoperability and ruleset/content packs after ABI freeze.

## Scoped Follow-up

### core
- Remove presentation/run-service/browser/legacy clutter from the engine boundary.

### ui
- Stop owning `Chummer.Session.Web` and `Chummer.Coach.Web`.
- Keep workbench plus future `Chummer.Ui.Kit` ownership.

### hub
- Publish `Chummer.Play.Contracts`.
- Prepare clean seams for `chummer-hub-registry` and `chummer-media-factory`.

### mobile
- Align package ids with the canonical contract plane.
- Replace scaffolded bootstrap/session client/offline storage placeholders with real play runtime seams.

## Do Not Split Yet

- Do not split player and GM play repos apart.
- Do not split session relay away from Spider yet.

