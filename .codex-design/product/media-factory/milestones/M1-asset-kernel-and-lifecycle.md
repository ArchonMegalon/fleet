# M1 - Asset kernel and lifecycle backbone

## Goal

Build the common substrate that every render domain reuses.
This milestone should make the repo operationally coherent even before product-specific features are rich.

## Included

* job intake and validation
* job store and attempt history
* provider-run ledger
* binary store abstraction
* asset manifest store
* preview/thumbnail generation hooks
* retention, pinning, supersession, and cleanup engine
* local filesystem + object-storage test backends
* structured failure taxonomy

## Excluded

* rich document rendering features
* portrait-specific canonical selection UI behavior
* video-specific cost policies beyond shared scaffolding
* run-services cutover

## Detailed design

### 1. Persistence design

Use a relational store for metadata and an external binary store for bytes.
The metadata schema must be shared across all domains.

Key design rule:
**never persist feature-specific asset state that duplicates the shared lifecycle model.**

### 2. Job execution model

Use a two-stage execution model:

* accepted/queued
* running/completed/failed/cancelled

Worker execution should be driven by an interface such as `IMediaJobExecutor`.
Each domain executor registers by job kind.

### 3. Preview handling

The kernel should not know how to create every preview, but it should define the protocol:

* parent asset completes
* optional preview task triggers
* preview asset is persisted and linked
* manifest group is updated atomically or transactionally enough for recovery

### 4. Cleanup safety

Build janitor logic now, not later.
Even if expiry is disabled in early environments, the cleanup logic must exist and be tested.

### 5. Contract hardening

Finalize:

* `MediaRenderJobState`
* `AssetApprovalState`
* `AssetRetentionState`
* `MediaAssetManifest`
* `MediaRenderFailure`

These become foundations for all later milestones.

## Exit tests

* queued jobs execute and complete through the shared scheduler
* failures preserve attempt history and provider-run diagnostics
* assets get manifests and previews through the common model
* TTL sweeps remove expired, unpinned assets only
* supersession records are queryable
* local and object-storage backends both satisfy the same contract tests

## Notes to implementers

Resist the urge to build feature-specific tables now.
The whole point of M1 is to avoid a document system, portrait system, and video system each inventing separate asset bookkeeping.
