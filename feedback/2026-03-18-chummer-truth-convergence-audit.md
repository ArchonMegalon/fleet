# Chummer truth-convergence audit

Date: 2026-03-18
Audience: `chummer-vnext` captains, project maintainers, and Fleet operators
Status: injected fleet feedback

## Scope

This packet treats the active scope as these 11 repos:

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

`chummer5a` is intentionally excluded.

This is a public-surface audit of repo trees, READMEs/worklists, design canon, Fleet config, release posture, and deployment/access posture. It is not a line-by-line code review.

## Program verdict

The architecture is coherent, but the program still has a truth-convergence problem.

Central design already defines precedence, boundaries, package ownership, and milestone exits. The unresolved problem is that public readiness, repo role boundaries, package authority, and deployment posture are still being narrated differently in different places.

Call the program:

* strong on vision
* materially improved on structure
* still under-converged on truth

## Main cross-program problem

The same work is being described through multiple incompatible public stories:

* design canon says one thing
* repo roots still visually imply older ownership
* public guides and release shelves use mixed readiness language
* Fleet models maturity with a different vocabulary than design
* EA is operationally mature, but it must not become a shadow product-definition system

The next milestone is not a new feature. It is getting every repo and control plane to tell the same truth.

## Forced priority order

1. Design + Fleet + Guide: unify public-status truth first.
2. Core + Hub + Mobile: close `A1`, `A2`, and `D1` by making engine/session semantics visibly single-owned.
3. Hub + Hub-registry + Media-factory: finish authority transfer, not just package extraction.
4. UI + UI-kit: make the tree and dependency graph prove the split.
5. EA last: harden runtime/provider truth while keeping EA subordinate to design canon.

## Repo-level change guide

### `Chummer6`

Public-status drift is the main defect. Downstream guide status currently mixes:

* stable wording
* preview wording
* POC wording
* protected-preview access posture

Required direction:

* generate guide readiness from one canonical status artifact
* separate `installability`, `promotion state`, and `access posture`
* keep this repo signoff-only and downstream-only

### `chummer6-design`

This is the structurally strongest repo in the family.

Required direction:

* make design the compiler input for Fleet, EA, and the guide instead of letting them maintain their own summary truth
* add explicit status classes such as `repo_local_complete`, `package_canonical`, `boundary_pure`, and `publicly_promoted`
* publish one canonical public-status artifact for downstream consumption

### `chummer6-core`

Mission is right; repo body is still wrong.

Required direction:

* make the root tree visibly engine-only or explicitly quarantine legacy/application/browser/tooling cargo
* create the engine-boundary doc already referenced by the README
* add verifier coverage for repo shape and visible ownership, not just semantic code behavior

### `chummer6-ui`

UI is feature-forward and boundary-late.

Required direction:

* treat `B2` as root surgery, not more feature work
* make the release story honest: either publish releases from this repo or clearly point to the actual release system of record
* enforce `ui-kit` consumption with CI so shared primitives stop reappearing locally

### `chummer6-mobile`

Mobile is the healthiest product-head repo.

Required direction:

* spend the next round on cross-repo canon proof instead of local features
* clean up repo-surface trust paper cuts like `/docker/...` README links and dual-name docs
* add CI guards against DTO duplication, UI-kit copy-back, or boundary creep

### `chummer6-hub`

Hub is the most important unresolved hosted-boundary repo.

Required direction:

* stop source-owning media contracts in the active hub boundary
* reduce registry work to adapter/composition responsibility around the real registry boundary
* treat shrink-to-fit as a visible tree outcome, not just README language

### `chummer6-ui-kit`

UI-kit is a real boundary, but downstream proof still matters more than internal completeness.

Required direction:

* define success as downstream duplication becoming impossible
* ship CI guardrails into UI and mobile
* delay broader ambition until `B1` is proven by downstream adoption

### `chummer6-hub-registry`

Hub-registry is a clean extraction seed, but package existence is not the same thing as transferred authority.

Required direction:

* stop calling it done before write/read-model authority actually leaves hub
* publish an owner-transfer scoreboard for remaining registry seams
* rename downstream docs to current topology instead of old split-era names

### `chummer6-media-factory`

Media-factory is honest and early.

Required direction:

* move from scaffold/doc truth to obviously-running service truth
* keep contracts render-only and exclude narrative/session/policy ownership
* reduce queue-overlay churn when evidence already covers the active head

### `fleet`

Fleet is strong, but it is still one of the main places where parallel truth can persist.

Required direction:

* stop hand-maintaining a second architecture brain
* generate public-status and milestone posture from design canon plus verification evidence
* unify Fleet lifecycle/maturity language with design language

### `executive-assistant`

EA is operationally mature and structurally serious, but it must remain product-subordinate.

Required direction:

* make every Chummer-specific skill consume canonical design/public-status inputs instead of free-reading repo surfaces
* finish runtime-boundary hardening around provider registry truth, startup/runtime-profile validation, and typed workflow/provider/skill metadata
* preserve fail-loud behavior when Chummer-specific lanes are unavailable

## Fleet-specific follow-through

Fleet should treat this packet as work to materialize, not just to display.

Required Fleet outcomes:

* one canonical public-status payload compiled from design truth plus deployment/access posture
* group and project maturity semantics aligned with canonical design status classes
* admin/cockpit views that distinguish delivery progress from design progress
* queue generation that prefers convergence work when public/readiness truth is drifting

## What to queue next

The next Chummer/Fleet coordination slices should be:

1. compile one canonical public-status artifact from `chummer6-design` plus deployment/access truth
2. make Fleet and the guide consume that artifact instead of handwritten summaries
3. add explicit status-class translation from design canon into Fleet lifecycle/maturity UI
4. audit core/ui/hub roots for visible ownership drift and turn the findings into executable cleanup slices
5. add CI and verifier guards that prove the split instead of merely describing it

## Bottom line

Vision is still good.

The split is most convincingly real in mobile and UI-kit.

Core, UI, and hub still need physical repo-body surgery.

Hub-registry and media-factory still need authority transfer proof.

Fleet must stop being a parallel truth layer.

EA must stay runtime-strong without becoming a shadow product-definition system.

The next milestone is truth convergence.
