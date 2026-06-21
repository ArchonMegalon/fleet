# Part 06 - Service integration

## 1. Purpose

The split is only real when `run-services` stops executing renderer code and treats media-factory as an internal dependency.

This part defines the runtime edge between the two repos.

## 2. Topology

* clients talk to `run-services`
* `run-services` talks to `media-factory`
* `media-factory` talks to storage and providers
* clients never talk directly to `media-factory`

## 3. Integration styles

### Phase 1: polling

`run-services` submits a job and polls job/asset status.
This is simple and good enough for early milestones.

### Phase 2: signed callbacks

`media-factory` sends a signed completion/failure callback.
This reduces polling pressure for long video jobs.

Both modes should be supported eventually, but polling should land first.

## 4. Submission contract

Every submission should carry:

* `JobKind`
* `RenderPlan`
* `IdempotencyKey`
* `CorrelationId`
* `RequestedByService`
* `RetentionPolicy`
* `Priority`
* optional callback ref

The caller is responsible for packaging any business context into the render plan or correlation metadata.
Media-factory must not fetch campaign data ad hoc.

## 5. Result contract

Every status/result should expose:

* `JobId`
* `State`
* `Progress`
* `PrimaryAssetId`
* `AssetHandles`
* `Warnings`
* `FailureCode`
* `Retryable`
* `LineageRefs`
* `CompletedAtUtc`

## 6. Idempotent cutover rule

During migration, `run-services` may still have legacy code paths.
The cutover must guarantee:

* one logical media request => one idempotency key
* retries do not duplicate cost-heavy jobs
* fallback/rollback never creates parallel final artifacts silently

## 7. Dependency rule

`run-services` may depend on:

* `Chummer.Media.Contracts`
* an internal media client package if one is created

`play` and `presentation` must not depend on the media-factory client directly.
They keep consuming upstream projections from `run-services`.

## 8. API sketch

Suggested routes:

* `POST /api/media/jobs`
* `GET /api/media/jobs/{jobId}`
* `POST /api/media/jobs/{jobId}:cancel`
* `GET /api/media/assets/{assetId}`
* `POST /api/media/assets/{assetId}:pin`
* `POST /api/media/assets/{assetId}:supersede`
* `POST /api/media/internal/callbacks/job-complete`

The public product APIs remain in `run-services`.

## 9. Cutover strategy

1. create media package and internal client
2. dual-write receipts if needed for observability only
3. move document rendering first
4. move portrait execution next
5. move video last
6. remove dead code from `run-services`
7. forbid renderer execution in `run-services` by lint or path ownership rule

## 10. Tests

Integration tests must prove:

* `run-services` can submit and observe completion
* duplicate submissions with the same idempotency key do not duplicate jobs
* callback signatures validate
* network failures surface as structured retryable failures
* client repos remain insulated from the internal media API
