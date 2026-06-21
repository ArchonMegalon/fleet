# Vision and milestones

## 1. Why this repo exists

Project Chummer already has a strong media seam, but it is still stranded inside `chummer6-hub`.
The system already wants a dedicated repo because:

* the central split order places `chummer6-media-factory` after the contract and UI/registry splits
* the ownership matrix says `run-services` must not own media rendering after the split
* the hosted-service design already names concrete asset-factory components
* the current media contracts already reference a missing `Chummer.Media.Contracts` package

In other words: the seam is real, but the repo is not yet fully materialized.

## 2. Product vision

`chummer6-media-factory` is the internal studio and render plant for Chummer.

It should eventually feel like three things at once:

* a **print shop** for packets, dossiers, bulletins, and summaries
* a **portrait and poster lab** for character/NPC imagery with review and canonicalization
* a **bounded video house** for route clips, NPC messages, and recap/news videos that stay under operational control

The repo succeeds when upstream services can ask for media confidently without re-implementing rendering, storage, lifecycle, or provider-specific quirks.

## 3. Product shape

### In scope

* render plans to finished artifacts
* previews, thumbnails, manifests, and signed asset access
* render job state machine and retries
* retention, expiry, pinning, and canonicalization
* provider adapter isolation
* auditability and cost control for heavy asset jobs

### Out of scope

* campaign state and memory truth
* rules reasoning
* lore retrieval
* approvals policy
* player delivery policy
* prompt persona authoring for general assistants
* user-facing UI

## 4. First-release target

v1 of this repo is not "all possible media."
It is the minimum complete set that makes the split real:

1. `Chummer.Media.Contracts` published and adopted
2. shared job + asset kernel
3. deterministic packet/news document rendering
4. portrait rendering with canonical selection and reroll lineage
5. bounded video execution for route clips and NPC messages
6. integrated cutover from `run-services`
7. operational hardening

## 5. Milestone map

## M0 - Repo and contract reset

Establish the repo, publish the package, and move media vocabulary out of `run-services`.
No renderer logic moves until this is done.

## M1 - Asset kernel and lifecycle

Build the common job, manifest, binary-store, preview, and retention backbone.
Every later feature must land on this substrate.

## M2 - Deterministic document rendering

Ship packet/dossier/news rendering from finalized content models and template packs.
This is the first "real value" milestone because it proves the split without the cost volatility of image/video providers.

## M3 - Portrait Forge

Move portrait generation and review/canonicalization into the repo.
The deliverable is not only "image generation works"; it is also "portrait lineage is managed safely."

## M4 - Video pipeline

Add bounded route clips, NPC video messages, and optional news video flow.
Video must launch with explicit cost guards and preview-first strategy.

## M5 - Integration and cutover

Replace any direct render execution in `run-services` with internal API calls to media-factory.
No client repo gains direct media-factory dependency.

## M6 - Hardening and release readiness

Make the repo production-safe: observability, quotas, DR, storage sweeps, structured failure handling, and SLOs.

## 6. Delivery philosophy

This repo should be built as a boring, dependable internal service.
Avoid the temptation to make it "smart."
Smartness already exists upstream in the AI gateway, retrieval, coach, and director flows.

The right bar is:

* small API surface
* stable contracts
* predictable costs
* understandable failure behavior
* easy local test harnesses
* easy provider substitution

## 7. GA definition

The repo reaches GA when all of the following are true:

* there is one canonical media contract package
* every major media flow uses the shared job/asset kernel
* no direct rendering remains in `run-services`
* binary asset storage is externalized and lifecycle-managed
* cutover can be rolled back without losing lineage or approval history
* ops can answer "what happened to this asset/job?" from logs, manifests, and provider-run records

## 8. Roadmap after GA

These are explicitly post-v1:

* reusable public template/style packs published through `chummer6-hub-registry`
* richer asset derivation graphs
* batch render farms and autoscaling
* advanced text-layout engines and typography packs
* multi-provider A/B evaluation for video render quality
* workflow-specific moderation or legal-hold states
* offline archival export bundles

## 9. Anti-roadmap

Do not treat these as v1 goals:

* "one giant AI content studio"
* arbitrary user prompt playgrounds
* direct browser/mobile media execution
* campaign memory authoring inside this repo
* freeform chatbot behavior
* public registry, moderation, or marketplace ownership
