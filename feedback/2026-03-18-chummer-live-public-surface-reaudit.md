# Chummer live public-surface re-audit

Date: 2026-03-18
Audience: `chummer-vnext` captains, repo maintainers, and Fleet operators
Status: injected fleet feedback

## Scope

Re-audit scope:

* `Chummer6`
* `chummer6-design`
* `chummer6-core`
* `chummer6-ui`
* `chummer6-mobile`
* `chummer6-hub`
* `chummer6-ui-kit`
* `chummer6-hub-registry`
* `chummer6-media-factory`
* `fleet`
* `executive-assistant`

This pass re-audits live public repo surfaces after the recent update wave. It is a public-surface audit of repo trees, READMEs, worklists, canonical milestones, Fleet config, releases, and visible deployment posture. It is not a line-by-line code review.

## Program verdict

This pass is more favorable than the previous one.

Honesty, boundary docs, queue discipline, and central-design linkage all improved. The program is more believable than before, but the canonical blocker set still keeps `A0`, `A1`, `A2`, `C1`, and `D1` open.

Call the current state:

* more aligned than before
* materially more credible
* still not converged enough to call release-ready

## What improved in this wave

The update wave fixed several credibility defects from the prior audit:

* the guide now labels public surfaces as preview instead of stable
* `chummer6-core` now has the boundary doc it was missing
* `chummer6-hub` now shows real shrink evidence and a `legacy/` quarantine
* `chummer6-mobile` retired the stale `chummer-play` front-door identity and added a public rejoin/resume guarantee
* Fleet project configs for newer extracted repos now point at central `products/chummer/projects/*.md` scopes instead of old split-era repo-local design files

## Repo audits

### `Chummer6`

This repo is materially better than before.

The guide now explicitly says the public surfaces are still preview and not the final public shape. Central design defines the guide as downstream-only and not sovereign. Fleet models it as `signoff_only`, which is the correct operational posture.

Remaining issue:

* the guide still uses lively “street-ready/live app” language while the release shelf remains a March 11 pre-release POC and the README still warns that binaries are unstable

Current audit:

* improved and mostly honest
* still slightly ahead of the binary story

### `chummer6-design`

This is still the right command center.

The precedence stack is clear and the project-scope docs are now substantive enough to act as real implementation contracts. But `BLK-001` still says the design repo is not yet fully canonical, `A0` remains open, and the horizon/public-guide/export-policy side of the program is still open.

Current audit:

* structurally strong
* still a live release blocker

### `chummer6-core`

Credibility improved in exactly the right places.

`docs/ENGINE_BOUNDARY.md` now exists, the README is honest that the repo body is still heavier than it should be, and the worklist names remaining cleanup as real queued work.

Remaining issue:

* the root tree still shows `Chummer.Application`, `Chummer.Contracts`, browser infrastructure, `Chummer.Run.Contracts`, `Chummer`, and `Plugins`
* central design still keeps `A1` open and boundary purity remains low

Current audit:

* better documented
* still not physically purified enough to claim engine-only credibility

### `chummer6-ui`

This repo still shows feature maturity outrunning boundary maturity.

The worklist now correctly focuses live work on UI-kit guardrails and boundary cleanup rather than missing feature lanes. The README openly says `B2` stays open until the repo body stops looking like the old presentation root.

Remaining issue:

* the tree still reads like the old presentation root
* GitHub still shows no releases here even though the README says the release lane ships installer-capable desktop bundles

Current audit:

* locally feature-rich
* architecturally under-purified
* release source-of-truth mismatch still unresolved

### `chummer6-mobile`

This remains one of the healthiest repos in the set.

The README now has crisp package-only boundary language, the public rejoin/resume guarantee exists, the worklist says major local closure is done, and the stale `chummer-play` identity has been retired.

Remaining issue:

* the unfinished work is now mostly cross-repo semantic-canon proof, especially `D1`

Current audit:

* healthy split
* narrow mission
* waiting on semantic-canon convergence rather than repo cleanup

### `chummer6-hub`

This repo improved the most in visible shrink evidence.

The root now includes a `legacy/` subtree, `HOSTED_BOUNDARY.md` is substantive, `HUB_EXTRACTION_ACCEPTANCE.md` is detailed, and the worklist has collapsed to a small number of structural tasks.

Remaining issue:

* `HOSTED_BOUNDARY.md` still lists `Chummer.Media.Contracts` and `Chummer.Run.Registry` inside the active hosted boundary
* the milestone file still keeps `A2`, `A3`, `C0`, `C1`, `C2`, and `D1` open

Current audit:

* substantially improved
* still too authoritative on active repo surface to call the cutover complete

### `chummer6-ui-kit`

This now reads like a real package repo rather than a placeholder.

The README documents concrete token, adapter, accessibility, and release-discipline expectations. The worklist makes the remaining B1/U4/U5/U7/U8 work executable.

Remaining issue:

* downstream proof is still the blocker
* Fleet still models the repo as `scaffold`

Current audit:

* credible shared-boundary repo
* still waiting on downstream deletion-and-guard evidence before B1 can honestly close

### `chummer6-hub-registry`

This remains the cleanest extraction seed in the family.

The root is compact, the README is crisp, and the worklist has collapsed to real owner-transfer tasks instead of package-seeding tasks.

Remaining issue:

* authority transfer is still the missing proof
* the worklist still frames unresolved state in old `run-services` terms

Current audit:

* clean package boundary
* incomplete operational ownership transfer

### `chummer6-media-factory`

This repo looks better than Fleet’s current model gives it credit for.

The README now explicitly says `Chummer.Media.Contracts` is the canonical render-only contract plane, and the worklist says the package plane, seam expectations, asset-kernel backlog, and render-only DTO boundary are done.

Remaining issue:

* running-service proof still lags
* Fleet milestone text is stale and still describes media contracts as if they were not yet real

Current audit:

* documentation and package canon materially improved
* running-service proof still missing
* Fleet needs a refresh immediately

### `fleet`

Fleet is better than before, but it is still not a perfect compiler of current truth.

The Chummer group now explicitly covers the right repo set, the guide is modeled as `signoff_only`, deployment posture is explicitly `protected_preview`, and newer repo configs point at central scope docs.

Remaining issue:

* modeled-state lag still exists in program milestones and project maturity descriptions
* mobile, hub-registry, and media-factory are still being narrated with stale maturity text

Current audit:

* Fleet stopped pointing at the wrong docs
* Fleet still narrates yesterday’s maturity model in several places

### `executive-assistant`

EA remains operationally the most mature adjacent repo and has clearly grown.

The root now contains a `chummer6_guide` workspace, the runtime and skills layer are explicit, and Chummer-specific skills are plainly surfaced. The README says Chummer text generation routes through EA + Gemini Vortex only and fails rather than silently falling back.

Remaining issue:

* runtime-governance closure is still open by Fleet’s own solo-EA milestones
* provider-registry truth, authoritative runtime-profile resolution, typed metadata closure, and docs/deployment alignment are still unfinished

Current audit:

* real runtime
* useful Chummer-adjacent executor
* not yet a fully typed and provider-governed control plane by its own standards

## Forced follow-through

This update wave mostly improved honesty, boundary docs, queue discipline, and central-design linkage. It did not clear the release-critical seams.

Fleet should materialize follow-through around:

1. refreshing stale per-project maturity/milestone descriptions from canonical design truth
2. keeping public-surface status honest across guide, Fleet, and deployment posture
3. continuing physical repo-body cleanup for core, UI, and hub
4. proving operational owner transfer for hub-registry and media-factory
5. keeping `A1`, `A2`, `C1`, and `D1` visible as unresolved release-critical seams until canon actually closes them

## Bottom line

The system is more believable now than in the last audit.

It is not release-ready yet.

The strongest improvements were honesty, boundary documentation, shrink evidence, and better linkage back to central design.

The next convergence target is not another new feature wave. It is finishing the remaining canonical seams and updating Fleet so it stops narrating stale maturity truth.
