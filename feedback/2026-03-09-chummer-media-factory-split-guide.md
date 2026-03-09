# chummer-media-factory split guide

Date: 2026-03-09
Audience: Project Chummer maintainers and Codex worker agents
Status: contract-first split guide for the missing `chummer-media-factory` repo

## Summary

`chummer-media-factory` should be the render-only asset execution plant for Project Chummer:

- render jobs in
- binary artifacts out
- manifests, lineage, thumbnails, TTL, and retention tracked

It must not become a second `run-services`:

- no rules math
- no session truth
- no Spider policy
- no delivery policy
- no prompt-registry ownership
- no general AI routing ownership

## Current blocker

The split should not be bootstrapped as a real repo boundary until the media contract plane is cleaned:

- `Chummer.Run.Contracts.Media` still mixes render lifecycle and narrative-generation DTOs
- the package plane for `Chummer.Media.Contracts` is not yet real
- render-only DTOs are not yet isolated from play/delivery/orchestration concerns

## Required direction

1. Create a canonical `Chummer.Media.Contracts` package.
2. Move asset/job/review/lifecycle/render DTOs there.
3. Keep editorial choice, delivery state, approvals policy, and campaign/session context in `run-services`.
4. Treat newspaper/news/NPC-video work as two layers:
   - upstream composition/drafting in `run-services`
   - downstream render execution in `chummer-media-factory`

## Repo mission

`chummer-media-factory` owns:

- `Chummer.Media.Contracts`
- render job state machine
- asset manifests and lineage
- thumbnails, previews, retention, expiry, pinning, supersession
- renderer/provider adapters
- binary storage abstraction

It must not own:

- campaign/session truth
- player delivery state
- approvals workflow policy
- lore retrieval
- Spider logic
- auth/identity
- UI/browser/mobile code

## Milestone shape

- `M0`: create `Chummer.Media.Contracts` and split render-only versus narrative-generation DTOs
- `M1`: asset/job/lifecycle kernel
- `M2`: deterministic packet/news/document rendering
- `M3`: portrait forge split
- `M4`: video pipeline split
- `M5`: internal service integration with `run-services`
- `M6`: hardening, observability, and release readiness

## Immediate Chummer tasks

- split `MediaContracts.cs` into render-only versus narrative-generation families
- define `Chummer.Media.Contracts` as the only cross-repo home for media DTOs
- keep `run-services` as orchestration, approvals, delivery, and grounding owner
- treat `chummer-media-factory` as blocked until the render-only contract plane is real
