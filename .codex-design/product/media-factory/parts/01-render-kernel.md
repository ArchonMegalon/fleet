# Part 01 - Render kernel

## 1. Purpose

The render kernel is the shared substrate beneath every media feature in the repo.
If the kernel is wrong, every later feature will re-implement queueing, retries, manifests, previews, and retention in slightly different ways.

The kernel exists to answer these questions uniformly:

* how is a job created?
* how is a job validated?
* how is work queued and retried?
* how are binaries stored and described?
* how are previews generated?
* how is lineage preserved?
* how do we expire, pin, and supersede assets?

## 2. Components

### `MediaJobIntakeService`

Validates incoming render plans.
Enforces idempotency keys, contract version checks, and target-specific validation before work enters the queue.

### `MediaJobStore`

Persists job state, attempts, progress, and structured failure information.
This store is the source of truth for execution state.

### `MediaJobScheduler`

Moves jobs from accepted state to worker execution.
It should support local/in-memory execution for tests and durable queue backends for production.

### `MediaBinaryStore`

Abstracts object storage or filesystem-backed blobs.
It exposes write, read-handle, delete/expire, checksum verify, and preview-derivation operations.

### `MediaAssetManifestStore`

Stores durable metadata for every produced artifact:
content type, size, dimensions, duration, checksum, preview refs, lineage refs, retention state, and canonical status.

### `ProviderRunLedger`

Persists provider-specific attempt metadata:
provider name, request token, quota/cost hints, latency, returned IDs, failure codes, and sanitized diagnostics.

### `PreviewThumbnailService`

Generates stable preview derivatives for assets.
This service must be reusable by documents, portraits, and videos.

### `AssetLifecycleService`

Applies retention, pinning, expiry, supersession, and canonical-selection changes.
It never decides *policy*; it only executes it.

## 3. Data model

Required logical entities:

* `MediaJob`
* `MediaJobAttempt`
* `MediaAsset`
* `MediaAssetPreview`
* `MediaAssetReview`
* `MediaAssetPin`
* `MediaAssetSupersession`
* `ProviderRun`
* `RetentionPolicyBinding`

Suggested minimum fields:

### `MediaJob`

* `JobId`
* `JobKind`
* `State`
* `IdempotencyKey`
* `RequestedAtUtc`
* `StartedAtUtc`
* `CompletedAtUtc`
* `CorrelationId`
* `PlanHash`
* `PrimaryAssetId`
* `FailureCode`
* `FailureSummary`

### `MediaAsset`

* `AssetId`
* `AssetKind`
* `Role`
* `StorageLocator`
* `Checksum`
* `ContentType`
* `ByteLength`
* `Width`
* `Height`
* `DurationMs`
* `RetentionState`
* `ApprovalState`
* `ExpiresAtUtc`
* `IsPinned`
* `SupersedesAssetId`
* `CanonicalGroupId`

## 4. Job state machine

Minimum state graph:

```text
accepted -> queued -> running -> completed
                 └-> failed
                 └-> cancelled
                 └-> timed_out
completed -> superseded
```

Rules:

* jobs are append-only in spirit; updates should preserve attempt history
* `cancelled` means no new provider execution may start
* `superseded` is an asset/lifecycle concept, not a job re-open
* `completed` does not imply approved or deliverable

## 5. Idempotency

Idempotency is mandatory.

The intake service must accept a caller-supplied idempotency key and a stable plan hash.
Duplicate submits with the same idempotency key and equivalent plan should return the existing receipt.
Duplicate submits with the same key but different plan hash must fail loudly.

## 6. Storage model

Production storage should be object storage first.
Local development may use disk-backed storage.

Rules:

* binaries never live inline in the relational store
* manifests always include checksum and byte length
* previews and thumbnails are separate assets, not ad hoc blobs
* signed URLs must be short-lived
* deletion is lifecycle-driven, never "whoops, remove this row"

## 7. Preview model

Every render type should define a preview policy.

* documents: page image + thumbnail
* portraits: dossier preview + thumbnail
* route videos: still image or short teaser clip
* NPC video: poster frame + short preview when economical

Preview generation should be queued as dependent jobs only when it materially changes cost or latency; otherwise it can run in-process within the completing worker.

## 8. Provider adapter interface

All external engines must sit behind narrow interfaces.

Suggested contracts:

* `IDocumentRenderer`
* `IImageRenderer`
* `IVideoRenderer`
* `IThumbnailRenderer`

Every adapter result should normalize:

* provider run id
* raw artifact locator/bytes
* content type
* checksum if available
* warnings
* cost/credit estimate if known
* retryability classification

## 9. Failure handling

Do not leak vendor-specific junk upstream.
Translate failures into a small internal taxonomy:

* validation failure
* provider unavailable
* provider rejected request
* quota exceeded
* content unsafe/restricted
* timeout
* corrupted output
* storage write failure
* internal execution error

The raw vendor diagnostics belong in the provider ledger, not in public result DTOs.

## 10. Tests

Kernel-level tests must prove:

* idempotent submit works
* state transitions are legal
* retries preserve attempt history
* previews are linked to parent assets
* pinned assets survive TTL sweeps
* supersession does not destroy lineage
* local and object-storage backends both pass the same contract harness

## 11. Anti-goals

* no campaign/session joins inside the kernel
* no UI strings in kernel state
* no provider SDK objects escaping the adapter boundary
* no feature-specific job tables if a shared kernel table can serve
