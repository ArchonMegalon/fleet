# Chummer Group Next Split Follow-up

Date: 2026-03-09
Scope: `group:chummer-vnext`

## Audit Summary

- `chummer-play` is the correct repo split, but it is still an extraction in progress rather than a fully sealed boundary.
- The contract plane is still not real enough: package naming drifts between `Chummer.Contracts` and `Chummer.Engine.Contracts`, and `Chummer.Play.Contracts` is still missing as a public package.
- `chummer-presentation` still owns session/mobile shell surface that should continue moving into `chummer-play`.
- `chummer-core-engine` and `chummer.run-services` still carry mixed-authority legacy surface beyond their intended clean repo boundaries.

## Recommended Split Order

1. Make the contract plane real.
2. Split out `chummer-ui-kit`.
3. Split out `chummer-hub-registry`.
4. Split out `chummer-media-factory`.
5. Move legacy tools/interoperability into their own repo later.
6. Split rulesets/packs only after the capability ABI and RuntimeLock are stable.

## Immediate Chummer Group Tasks

- Canonicalize package naming on `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Run.Contracts`.
- Publish a real `Chummer.Play.Contracts` package before treating the play seam as complete.
- Create `chummer-ui-kit` as a package-only UI boundary shared by Presentation and Play.
- Keep player and GM play shells together for now; do not split them again before the play substrate is real.

## Queue Guidance

- `core`: remove authority leakage and package drift from the engine-owned contract plane.
- `ui`: finish removing play/mobile shell ownership and package-canonicalize UI dependencies.
- `hub`: publish `Chummer.Play.Contracts` and continue splitting hosted contract families by domain.
- `mobile`: replace scaffold seams with the real play API, browser persistence, and sync/runtime bundle consumption.
- `group:chummer-vnext`: bootstrap `chummer-ui-kit` next once the current contract plane tasks are unblocked.
