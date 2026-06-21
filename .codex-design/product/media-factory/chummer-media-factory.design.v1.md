# chummer6-media-factory.design.v1.md

Version: v1.0
Status: proposed authoritative repo design
Audience: Staff/Principal design review, worker-agent implementation, release planning

## 1. Mission

`chummer6-media-factory` is the dedicated rendering and media-generation runtime for Project Chummer.

It exists to take **prepared, reviewable, grounded upstream plans** and turn them into:

* portraits and portrait variants
* dossier packets, memos, forms, and PDFs
* previews, thumbnails, share cards, and print assets
* route clips and bounded recap/video artifacts
* NPC message videos and other delivery-safe media outputs

The repo is intentionally **execution-first**, not orchestration-first.

It is a render plant, print shop, and artifact warehouse - not the campaign OS, not the AI gateway, and not the rules engine.

## 2. Ownership

### 2.1 This repo owns

* `Chummer.Media.Contracts`
* media job vocabulary and asset vocabulary
* media job state machines
* provider adapters for image, PDF, preview, thumbnail, and video rendering
* asset manifests and binary-location abstraction
* retention, expiry, pinning, canonical selection, and supersession execution
* preview generation and artifact assembly
* render-specific validation and deterministic template filling
* storage abstraction and asset checksum/content-hash discipline
* worker queueing, retry, and provider-run audit records
* metrics and operational safety for heavy artifact workloads

### 2.2 This repo must not own

* Shadowrun mechanics or rules evaluation
* RuntimeLock generation
* campaign/session memory truth
* AI provider routing for general chat/reasoning
* prompt-registry ownership for broad assistant flows
* who may receive or view an artifact
* approvals policy or canon policy
* hub publication or moderation
* player-facing/mobile/browser UI
* design system primitives
* registry persistence for reusable public artifacts

## 3. Cross-repo boundary model

### `chummer6-core`

Supplies semantic seeds only: aesthetic digests, character labels, dossier seed models, route seeds, and provenance metadata.
It never renders and never stores heavy generated binaries.

### `chummer6-hub`

Owns orchestration and business meaning:

* decides that a job should exist
* gathers campaign/session context
* drafts text/scripts upstream
* performs approvals and delivery
* maps finished assets into campaigns, messages, memories, or hub records

`run-services` submits render work but must stop owning renderer execution.

### `chummer6-hub-registry`

Owns publication and immutable reusable artifacts:
template packs, style packs, poster/report templates, and public asset metadata when those assets are meant to be installed and reused.
It does not own per-session draft media execution.

### `chummer6-mobile` and `chummer6-ui`

Consume only approved asset handles, status DTOs, and preview data from upstream services.
They never call render vendors and never store provider secrets.

### `chummer6-ui-kit`

Owns tokens, themes, shell chrome, approval chips, banner primitives, and view components only.
It owns no media DTOs and no media business state.

## 4. Design principles

1. **Grounded before generative**
   This repo renders from prepared plans. It does not invent meaning.

2. **One substrate, many products**
   Portraits, PDFs, thumbnails, and videos reuse a common job/asset/lifecycle backbone.

3. **Artifacts are immutable; lifecycle is mutable**
   The bytes do not change after completion. Approval, retention, and canonical state can change.

4. **Preview-first where possible**
   Especially for expensive video flows, cheap previews should front-run costly full renders.

5. **Cache aggressively; pin intentionally**
   Heavy assets are disposable unless explicitly retained.

6. **No app server should be a CDN**
   Assets live in object storage. APIs return manifests and signed URLs.

7. **Provider failures are ordinary events**
   Every adapter must fail with structured diagnostics and no orphaned state.

8. **Deterministic where we can, bounded where we cannot**
   Document rendering must be byte-stable for the same input model and template version. Image/video generation must preserve lineage and exact inputs.

## 5. Top-level architecture

```text
run-services
  └─ submits render plan + idempotency key + policy hints
       └─ media-factory API
            ├─ Job Intake / Validation
            ├─ Job Queue
            ├─ Render Executors
            │    ├─ Document Executor
            │    ├─ Portrait Executor
            │    ├─ Video Executor
            │    └─ Preview/Thumbnail Executor
            ├─ Asset Manifest Store
            ├─ Binary Store
            ├─ Provider Run Ledger
            ├─ Lifecycle/Retention Engine
            └─ Status/Receipt API
       └─ run-services polls or receives callback
            └─ attaches approved assets to campaigns/messages/registries
```

## 6. Contract plane

### 6.1 Package ownership

* `Chummer.Media.Contracts` - owned and published here
* `Chummer.Run.Contracts.Media` - stays in `run-services`; contains orchestration/composition DTOs only
* `Chummer.Engine.Contracts` - engine provenance or labels only; never media execution contracts

### 6.2 Core contract families in `Chummer.Media.Contracts`

* asset primitives
* job primitives
* review/lifecycle primitives
* template/style references
* document render models
* portrait render plans/results
* video render plans/results
* thumbnail/preview contracts
* structured failure/result envelopes

### 6.3 Forbidden contract coupling

No public type in `Chummer.Media.Contracts` may depend on:

* `Chummer.Play.Contracts`
* `Chummer.Ui.Kit`
* UI rendering types
* EF/database entities
* HTTP abstractions
* campaign/session DB context
* provider SDK types

## 7. Internal component model

### 7.1 Shared kernel

* `MediaJobIntakeService`
* `MediaJobScheduler`
* `MediaJobStore`
* `MediaAssetManifestStore`
* `MediaBinaryStore`
* `ProviderRunLedger`
* `AssetLifecycleService`
* `ContentHashService`
* `PreviewThumbnailService`

### 7.2 Document domain

* `RenderTemplateCatalog`
* `HtmlTemplateRenderer`
* `PdfRendererAdapter`
* `ImageRendererAdapter`
* `PacketRenderService`
* `IssueRenderService`

### 7.3 Portrait domain

* `PortraitForgeExecutor`
* `PortraitProviderAdapter`
* `PortraitVariantAssembler`
* `PortraitConsistencyStore`
* `CanonicalPortraitSelector`

### 7.4 Video domain

* `VideoRenderPlanCompiler`
* `RouteCinemaExecutor`
* `NpcVideoExecutor`
* `NewsVideoExecutor`
* `VideoPreviewGenerator`
* `VideoCostGuard`

### 7.5 Integration edge

* internal `/api/media/*`
* idempotent submission
* polling/callback receipts
* signed URL issuance
* structured result/failure projection

## 8. Persistence model

This repo should persist **manifests and execution state**, not campaign truth.

Required logical stores:

* `media_jobs`
* `media_job_attempts`
* `provider_runs`
* `media_assets`
* `asset_variants`
* `asset_supersessions`
* `asset_reviews`
* `asset_pins`
* `asset_previews`
* `retention_policies`
* `binary_locators`

All stores are keyed by durable IDs and safe for replay/reconciliation. Binary bytes live outside the relational store.

## 9. Security and compliance posture

* provider secrets live only in service infrastructure
* generated artifacts are addressed by signed URLs or short-lived fetch tokens
* uploaded anchors/references are virus-scanned and content-typed before use
* binaries are stored with checksum and size metadata
* moderation, canon approval, and delivery decisions stay upstream
* redaction or legal takedown is a lifecycle state transition, not ad hoc deletion

## 10. Milestone spine

* **M0** repo recreation and contract reset
* **M1** asset kernel and lifecycle backbone
* **M2** deterministic document rendering
* **M3** portrait forge split
* **M4** video pipeline split
* **M5** run-services integration and runtime cutover
* **M6** hardening and release readiness

Milestone detail lives in `milestones`.

## 11. Release bar

The repo is ready for v1 release when:

* `Chummer.Media.Contracts` is the sole cross-repo media contract source
* `run-services` no longer executes render logic directly
* one shared asset/job substrate serves all major media types
* asset lifecycle and storage policy are centrally enforced
* internal API is idempotent and observable
* preview/document/portrait/video flows survive provider failure without corrupting upstream state
* rollback and restore drills are documented and verified

## 12. Non-negotiable rules

* Never let campaign/session context leak into asset execution state.
* Never let client repos call media vendors directly.
* Never let `run-services` re-grow renderer execution once cut over.
* Never make document rendering depend on an LLM inside this repo.
* Never store heavy binaries on the API/app host filesystem in production.
* Never make "approval" a UI-only convention; it must be persisted.
