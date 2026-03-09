# Chummer Group Follow-Up Audit

Date: 2026-03-09
Scope: `group:chummer-vnext`

## Bottom line

`chummer-play` was the correct split, but the public repo graph still shows an extraction in progress rather than a fully completed separation.

## Main findings

- The mobile/play seam is now physically real in `chummer-play`, with dedicated play-mode projects and play-specific docs.
- The contract plane is still not real enough:
  - naming still drifts between `Chummer.Contracts` and `Chummer.Engine.Contracts`
  - `Chummer.Play.Contracts` is still missing as a public package/repo surface
  - package-only consumption is not yet enforced
- `chummer-play` itself is still scaffold-stage:
  - placeholder bootstrap path
  - placeholder browser session and coach clients
  - in-memory event-log storage instead of real browser persistence
- `chummer-presentation` still carries design and code ownership for session/mobile surfaces even though `chummer-play` now exists.
- `chummer-core-engine` still has the strongest authority leakage, including presentation/run-service contract trees and broad legacy/tooling residue.
- `chummer.run-services` is structurally much cleaner than before, but it still carries legacy/host clutter beyond a clean hosted boundary.

## Recommended split order

1. Make the contract plane real.
   - Standardize on `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Run.Contracts`.
   - Remove `Chummer.Presentation.Contracts` and `Chummer.RunServices.Contracts` source trees from `chummer-core-engine`.
   - Stop package-name drift before more repo splits happen.

2. Split `chummer-ui-kit`.
   - Own design tokens, shared layout primitives, accessibility primitives, stale-state badges, approval chips, offline banners, iconography, and motion policy.
   - Hard boundary: no domain DTOs, no HTTP clients, no local storage, no rules math.
   - Both `chummer-presentation` and `chummer-play` should consume it as a package only.

3. Split `chummer-hub-registry`.
   - Own publication, immutable artifacts, runtime bundle catalog, NPC vault, build-idea library, reviews, moderation, and install history.
   - Hard boundary: no AI routing, no Spider, no session relay, no lore/vector retrieval, no delivery outbox.

4. Optionally split `chummer-media-factory`.
   - Own dossier/news rendering, portrait jobs, thumbnails, route-video jobs, asset manifests, approval states, and asset lifecycle.
   - Hard boundary: no session relay, no campaign registry, no direct mechanics math.

5. Later only:
   - `chummer-legacy-tools` or `chummer-legacy-interop`
   - `chummer-rulesets` / `chummer-packs` after ABI and RuntimeLock freeze

## Explicit do-not-split-yet guidance

- Do not split player and GM play into separate repos yet.
- Do not split session relay away from Spider yet.
- First finish the shared play/session/offline contract seam and package plane.

## Immediate program guidance

- Treat the contract plane as the next mandatory group milestone.
- Keep `chummer-play` as the first play-only client repo, but do not call the split complete yet.
- Make `chummer-ui-kit` the next clean repo split if only one more repo is created now.

