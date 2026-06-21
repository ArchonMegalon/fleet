# Public Chummer repo audit

Date: 2026-03-10
Audience: `chummer6-design` and the `chummer-vnext` group
Status: injected fleet feedback

## Summary

The public Chummer repo split is now materially real:

* `chummer6-design`
* `chummer6-core`
* `chummer6-ui`
* `chummer6-hub`
* `chummer6-mobile`
* `chummer6-ui-kit`
* `chummer6-hub-registry`
* `chummer6-media-factory`

The remaining architectural problem is not whether the split exists. It does.

The problem is that the code graph has moved farther than the central design graph. The program is still design-led in theory and code-led in practice because `chummer6-design` continues to publish a stale pre-split worldview while the code repos have already crossed that line.

## Improvements confirmed

* `chummer6-design` now has the right skeleton: root README, `products/chummer/*`, repo scopes, review templates, and a sync manifest.
* `chummer6-mobile` now has a real `src/` tree instead of being docs-only.
* `chummer6-ui-kit` and `chummer6-hub-registry` both look like healthy seed splits with `.codex-design` mirrors and scoped source trees.
* `chummer6-ui` now has the most honest README in the graph and explicitly says the shipped `/session` and `/coach` heads belong to `chummer6-mobile`.

## Main problems

1. `chummer6-design` still publishes stale truth.
   - Active repo coverage still lags the real public graph.
   - The product README and milestone/blocker/contract truth still describe parts of the split as future work.
   - Canonical files are still too thin to steer the rest of the program safely.

2. `chummer6-design` still violates its own canonical-tree rule.
   - Root-level media-factory-specific docs and folders still exist outside `products/chummer/*`.
   - `chummer6-media-factory` is still not fully onboarded into the central design/mirror system.

3. Package canon is still drifting.
   - `chummer6-mobile` still has `Chummer.Contracts` versus `Chummer.Engine.Contracts` naming drift.
   - `chummer6-hub` still duplicates session relay/runtime bundle DTO families across play and run packages.

4. The newest split repos still have asymmetric maturity.
   - `chummer6-ui-kit` and `chummer6-hub-registry` are healthy seed repos.
   - `chummer6-media-factory` is still scaffold-stage and the least integrated split repo.

## Repo-by-repo assessment

### `chummer6-design` - red

Good skeleton, weak canon.

* Fix the repo graph first.
* Replace the stub or near-stub canonical files with real design truth.
* Onboard `chummer6-media-factory` everywhere central canon enumerates active repos, mirrors, scopes, ownership, milestones, blockers, and contracts.
* Move orphan product docs out of the repo root and into the canonical `products/chummer/*` tree.

### `chummer6-mobile` - red/yellow

The repo is past the docs-only stage, but it still has package and mirror drift.

* Resolve `Chummer.Contracts` versus `Chummer.Engine.Contracts` immediately.
* Make `.codex-design` mirror coverage visible and current.
* Keep the repo focused on becoming the first serious consumer-test of the package plane.

### `chummer6-media-factory` - red

The mission is right, but the repo is still mostly a placeholder split.

* Add a real source tree.
* Add full mirror coverage.
* Turn `Chummer.Media.Contracts` into a real package seam.
* Stop leaving media contract ownership ambiguous between media-factory and run-services.

### `chummer6-ui-kit` - green/yellow

Healthy seed split.

* Keep scope narrow and package-only.
* Use the design repo to publish the roadmap and component taxonomy that this repo itself should not invent ad hoc.

### `chummer6-hub-registry` - green/yellow

Healthy seed split.

* Keep growing it from contract seed to real registry behavior.
* Make `chummer6-design` describe it as an active governed repo, not a future recommendation.

### `chummer6-hub` - red/yellow

Real structural progress exists, but the repo is still too wide and still duplicates semantic transport families.

* Collapse the duplicate `SessionEventEnvelope` / runtime bundle / relay DTO families across play and run packages.
* Untangle `MediaContracts.cs` so run-services stops carrying mixed downstream media and play surface types.
* Rewrite the README to stop narrating the old multi-head runtime story.

### `chummer6-core` - red/yellow

Boundary purification is still not done.

* Remove obvious cross-boundary source leaks.
* Rewrite the README so it stops narrating `/hub`, `/session`, and `/coach` as part of the current core world.
* Keep quarantining legacy utility/app surface out of the active engine boundary.

### `chummer6-ui` - yellow

This repo is ahead of central design truth.

* Keep aligning local scope to the split the README already acknowledges.
* Narrow the broad legacy root surface over time.
* Keep `Chummer.Ui.Kit` consumption as a hard package-only rule.

## Priority order

1. Fix `chummer6-design` first.
2. Fix `chummer6-mobile` package canon and mirror coverage.
3. Fix `chummer6-media-factory` onboarding.
4. Collapse `chummer6-hub` contract duplication.
5. Keep purifying core and narrowing presentation.

## Worker instruction

Do not assume the current central design canon is fully current just because the repo exists.

When the code graph and the design repo disagree:

* update `chummer6-design` first
* freeze package names before adding more seams
* prefer package-only and mirror-first corrections over local repo improvisation
