# Chummer / Fleet / EA Program Change Guide

**Effective:** March 11, 2026

The live GitHub state is ahead of the older ZIP, but the program is currently more coordinated than it is purified. Fleet already runs Chummer as a lockstep group across `core`, `ui`, `hub`, `mobile`, `ui-kit`, `hub-registry`, `media-factory`, and `design`; at the same time, Fleet's own milestone registry still says group milestone coverage is incomplete, shared lockstep blockers are not first-class runtime data yet, the play extraction is incomplete, the UI kit is not yet a package-only boundary, and registry/media seams are still scaffold-stage. Fleet also marks every public Chummer surface it knows about as `stale_preview`.

At the same time, `chummer-design` is positioned as the canonical cross-repo design front door, but it is still too thin to carry the full weight Fleet is putting on it.

So this guide makes one directional reset explicit:

**From today forward, the dev group optimizes for truthfulness, deletion, and package-real boundaries, not for more scaffolds, not for more repo splits, and not for prettier architecture language.**

## 1. Non-negotiable decisions

`chummer-design` is the only canonical cross-repo design source. Code repos may keep mirrored local design guidance under mirror paths for workers and review, but those mirrors are consumers of design truth, not authors of it.

No new split is treated as success just because a repo exists. A split is only real when the package or API boundary exists, consumers are switched, the old owner deletes the old implementation, verification blocks regressions, and Fleet/design/README/deployment status all agree.

Across repo boundaries, only three dependency types are allowed:
- package consumption
- stable HTTP/API consumption
- design mirrors from `chummer-design`

The following are not allowed:
- copied contracts
- source-tree borrowing
- direct cross-repo project references

Public preview is not release truth. Any surface still marked `stale_preview` remains preview debt and cannot be used as evidence that the corresponding repo split is complete.

## 2. Canonical architecture and repo authority

`chummer-core-engine` owns deterministic engine truth: reducer behavior, explain canon, runtime compatibility, and the engine contract plane. It does not own shipped UI heads, hosted orchestration, registry persistence, or media rendering.

`chummer-presentation` owns workbench UX: browser/desktop heads, inspectors, builders, authoring surfaces, workbench-side launch/deep-link/session seams, and workbench-side coach sidecars. It does not own the shipped `/session` or `/coach` heads, provider logic, render execution, or duplicate design-system primitives once the UI kit is real.

`chummer.run-services` owns hosted identity, relay, approvals, memory, AI orchestration, and governed play APIs. It does not own duplicate engine semantics, registry persistence after the registry split, or render execution after the media-factory split.

`chummer-play` owns the player/GM/mobile shell, offline ledger handling, runtime bundle consumption, play-scoped coach/Spider surfaces, and PWA/offline/media cache behavior. It does not own builder UX, rule evaluation, provider secrets, or copied shared contracts.

`chummer-ui-kit` owns tokens, themes, shell chrome, accessibility primitives, and reusable cross-head UI primitives. It does not own DTOs, HTTP clients, storage, or rules math.

`chummer-hub-registry` owns immutable artifact metadata, publication flow, moderation flow, installs, compatibility projections, and runtime-bundle head projections. It does not own AI routing, Spider, relay, or media rendering.

`chummer-media-factory` owns render-only media lifecycle, queueing, storage adapters, signed URLs, dedupe/retry, and rendered-asset approval-state persistence. It does not own lore retrieval, narrative policy, provider routing, rules math, or session relay.

## 3. Immediate architecture correction: the contract plane

Naming drift in the contract layer ends now.

Directives:
- `Chummer.Engine.Contracts` is the explicit external engine contract package name.
- `Chummer.Contracts` may remain only as a temporary compatibility alias while consumers migrate.
- No repo may introduce a second canonical meaning for engine-owned contracts.

Required cross-repo package families:
- `Chummer.Engine.Contracts`
- `Chummer.Play.Contracts`
- `Chummer.Ui.Kit`
- `Chummer.Hub.Registry.Contracts`
- `Chummer.Media.Contracts`

Contract changes now follow this order:
1. design change
2. boundary decision
3. package implementation
4. consumer migration
5. old-source deletion
6. verification hardening
7. README/review-template update

## 4. Repo-by-repo operating orders

### `chummer-design`

This repo becomes real immediately. Its job is to hold product truth, repo ownership, milestone truth, blockers, review templates, mirror rules, and ADRs.

Required changes:
- turn `VISION.md` into an actual release-direction document
- turn `ARCHITECTURE.md` into a real repo graph and split protocol
- complete milestone coverage
- add repo-specific review templates
- add ADRs for contract canon, play split, UI-kit split, hub-registry split, and media-factory split
- publish mirror rules so Fleet sync is deterministic

### `fleet`

Fleet stays, but Fleet is not allowed to imply repo truth that the repos have not earned.

Required changes:
- add a purification scoreboard per repo
- block `done` status when README/design/deploy state disagree
- show stale public surfaces as debt, not completion
- expose lockstep blockers as runtime data
- stop treating scaffold repos as success markers

### `chummer-core-engine`

Required changes:
- finish A6/A7/A8/A9 work
- delete temporary cross-boundary contract source projects after package cutover
- strip session/coach/hub head ownership language from the repo's active identity
- keep helper tools outside active engine verification
- ensure downstream consumers get engine truth through package/API seams only

### `chummer-presentation`

Required changes:
- keep only workbench/browser/desktop ownership
- treat shipped `/session` and `/coach` as external play-owned surfaces
- remove provider/media/hosted claims unless genuinely owned
- adopt `Chummer.Ui.Kit` package-only the moment it is published
- delete duplicated tokens/themes/components after migration
- complete accessibility and browser-deployment signoff before public workbench promotion

### `chummer.run-services`

Required changes:
- publish canonical `/api/play/*` seams aligned to `Chummer.Play.Contracts`
- move registry ownership into `chummer-hub-registry`
- finish `Chummer.Media.Contracts` split and move render execution into `chummer-media-factory`
- keep AI orchestration, approvals, memory, relay, and identity here
- remove legacy/helper clutter from the active hosted boundary
- add stronger observability, idempotency, backup/restore, and clean-room boundary checks

### `chummer-play`

Required changes:
- replace placeholders with real migrated implementation
- keep package-only boundaries and zero project refs back into presentation/core
- align on `Chummer.Play.Contracts`
- harden local-first runtime, replay, sync, conflict, and cache behavior
- enforce role-gating so player flows cannot invoke GM actions
- complete installable PWA behavior

### `chummer-ui-kit`

Required changes:
- publish a real `Chummer.Ui.Kit` package
- own tokens, themes, chrome, badges, approval chips, offline banners, and accessibility primitives
- support both Blazor and Avalonia consumers
- keep previews/gallery UI-only
- force duplicate deletion in presentation and play after migration

### `chummer-hub-registry`

Required changes:
- fully move the `Chummer.Run.Registry` seam here
- keep the package immutable and dependency-light
- switch consumers to package/API use
- delete old source-level registry ownership from run-services

### `chummer-media-factory`

Required changes:
- define `Chummer.Media.Contracts` as render-only
- split lifecycle DTOs from narrative/provider-policy DTOs
- own queue/dedupe/retry/storage/signed URLs/rendered-asset approval-state
- reject lore/policy/provider-routing creep

### `executive-assistant`

This repo is not part of the Chummer split, but it is the strongest operational reference in the group. Chummer should borrow its discipline without inheriting domain sprawl or over-modeling.

## 5. Review, verification, and release rules

GitHub review gating stays where Fleet already requires it. Local review remains fallback-only except where a repo is explicitly configured otherwise.

`chummer-design` must publish repo-specific review templates, and Fleet must mirror them into each code repo. Reviewers are required to check:
- ownership drift
- package/source duplication
- stale README claims
- widened interfaces used to avoid real boundary work
- provider leakage into UI repos
- render leakage into non-render repos
- missing tests for new boundaries

Verification rules tighten by repo type:
- engine repos: determinism, normalization, explain/provenance, boundary guardrails
- presentation/play repos: no copied contracts, no cross-repo project refs, accessibility, offline/cache/PWA, deployment signoff
- hosted repos: contract verification, smoke tests, idempotency, observability, backup/restore
- boundary repos: compile checks plus consumer compatibility checks

## 6. Public deployment policy

Until promotion criteria are met, `/`, `/hub`, `/blazor`, `/session`, and `/coach` remain preview debt, not product truth.

Promotion requires:
1. clear repo ownership
2. README and design agreement
3. Fleet deployment status matching reality
4. canonical package/API boundaries
5. deletion of old duplicate ownership
6. passing verification
7. updated runbook/release notes

## 7. Execution sequence from here

Phase 1 is design canon and naming canon.
Phase 2 is contract reset.
Phase 3 is finishing `chummer-play`.
Phase 4 is making `chummer-ui-kit` real.
Phase 5 is moving registry into `chummer-hub-registry`.
Phase 6 is making `chummer-media-factory` render-only and real.
Phase 7 is shrinking `chummer-core-engine` and `chummer.run-services`.
Phase 8 is promoting deployments only after the code, docs, and public surfaces finally agree.

## 8. Behaviors that are now banned

These are banned across the dev group:
- calling a split `done` because a repo exists
- leaving old implementations behind after new ownership is declared
- copying contracts between repos
- using direct cross-repo project refs
- widening a local interface to bypass a boundary
- leaving README claims that contradict ownership
- treating stale public previews as shipped architecture
- leaking provider logic into UI repos
- leaking render execution into non-render repos
- closing milestones when design, code, Fleet, and deployment disagree

That is the new standard.
