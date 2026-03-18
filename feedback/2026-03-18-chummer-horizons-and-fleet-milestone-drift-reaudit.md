# Chummer Horizons And Fleet Milestone Drift Re-Audit

Date: 2026-03-18
Audience: `chummer-vnext` captains, guide maintainers, design leads, and Fleet operators
Status: injected fleet feedback

## Scope

This packet re-audits the same public repo set after the March 17-18 update wave:

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

## Program verdict

The update wave materially improved design canon, repo honesty, and central-design linkage. The biggest remaining drift centers are now:

* the guide’s non-canonical Horizons catalog
* Fleet’s stale milestone/maturity model

Canonical design still keeps `A0`, `A1`, `A2`, `C1`, and `D1` open as the release blockers.

## Highest-signal findings

### `Chummer6`

The front door is more honest than before about preview status, but Horizons are now the main drift point. Design now owns canonical `HORIZON_REGISTRY.yaml`, `HORIZONS.md`, and `PUBLIC_GUIDE_POLICY.md`, while the guide still carries a larger private Horizons catalog in `HORIZONS/README.md`.

Required follow-through:

* regenerate Horizons from design canon
* stop the guide from outrunning the design horizon registry
* keep tone aligned with the still-preview release shelf

### `chummer6-design`

This is now the strongest truth repo in the family. The canonical horizon/public-guide files exist and the worklist now directly targets the right compiler/generation tasks.

Remaining drift:

* `PROGRAM_MILESTONES.yaml` still leaves `A0` and the Horizons/public-guide lane open
* `GROUP_BLOCKERS.md` still keeps `BLK-001` red

Inference: the remaining work is now enforcement/generation and milestone-state advancement, not absence of canon files.

### `chummer6-core`

Documentation improved materially, but the root tree still advertises mixed ownership. The repo stopped bluffing, but it still does not physically read like a pure engine repo.

### `chummer6-ui`

UI now clearly separates feature completion from boundary completion, which is good. The root tree still looks like the old presentation super-repo, and the release-source-of-truth mismatch remains unresolved.

### `chummer6-mobile`

Mobile remains the healthiest execution repo. Remaining work is genuinely cross-repo semantic convergence, not repo self-confusion.

### `chummer6-hub`

Hub now explains its debt much better and shows visible shrink evidence. The active surface still carries too much authority for a claimed completed cutover.

### `chummer6-ui-kit`

UI-kit now reads like a real shared-boundary package. The blocker is downstream deletion-and-guard proof in consumers, not local repo ambiguity.

### `chummer6-hub-registry`

The package extraction is clean, but the repo still narrates owner transfer in old topology language and still needs real authority transfer proof.

### `chummer6-media-factory`

This repo is honest and clearer than before, but still visibly a contract-and-docs repo rather than a visibly running media plant. `C1` remains open on observable surface.

### `fleet`

Fleet is now accurate on deployment/access posture but remains the noisiest stale-state file set on Chummer maturity. `config/program_milestones.yaml` is still narrating yesterday’s maturity model.

### `executive-assistant`

EA remains operationally strong and increasingly governed by typed/runtime structures, but it still carries open runtime-governance debt around provider-registry canon and startup/runtime-profile truth.

## Required Fleet follow-through

Treat this packet as work to materialize, not just display.

Queue next:

1. regenerate the guide Horizons surface from `chummer6-design` canon
2. compile Fleet milestone and maturity modeling from `chummer6-design` instead of hand-maintained summaries
3. refresh Chummer repo maturity text where Fleet still contradicts current repo surfaces
4. keep public-access posture sourced from live deployment evidence, not optimistic prose

## Bottom line

Most improved: `chummer6-design`, `chummer6-hub`, and the public-status honesty in `Chummer6`.

Strongest current execution repos: `chummer6-mobile` and `chummer6-ui-kit`.

Largest remaining drift points: the guide’s non-canonical Horizons catalog and Fleet’s stale milestone model.

