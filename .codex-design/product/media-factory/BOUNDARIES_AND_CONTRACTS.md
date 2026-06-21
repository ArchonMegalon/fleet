# Boundaries and contracts

## 1. Boundary rule

**Media-factory owns execution and artifact lifecycle. Upstream repos own meaning, policy, and user flow.**

That rule should resolve nearly every boundary dispute.

## 2. Repo boundary matrix

| Repo                    | Owns with respect to media                                                                      | Must not own with respect to media                                                 |
| ----------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `chummer6-core`   | semantic seeds, labels, provenance, route or dossier seed data                                  | rendering, storage, provider adapters, approval state                              |
| `chummer6-hub`  | orchestration, drafting, approvals, delivery, campaign/session context, AI routing              | final renderer execution, binary lifecycle management, provider-specific job state |
| `chummer6-hub-registry`  | public/reusable template packs, style packs, immutable artifact metadata                        | per-session job execution, provider secrets, transient draft artifact storage      |
| `chummer6-mobile`          | display of approved assets and job state projections                                            | direct media submission, provider secrets, render orchestration                    |
| `chummer6-ui`  | workbench/admin/authoring UI, inspect and compare surfaces                                      | renderer execution, binary storage, contract ownership                             |
| `chummer6-ui-kit`        | tokens, themes, components, view primitives                                                     | DTOs, media clients, storage, render state                                         |
| `chummer6-media-factory` | `Chummer.Media.Contracts`, render jobs, asset manifests, lifecycle, previews, provider adapters | campaign truth, rules truth, approvals policy, public UI                           |

## 3. Package plane

## 3.1 Canonical packages

* `Chummer.Media.Contracts` - owned here; the only cross-repo home for media execution DTOs
* `Chummer.Run.Contracts.Media` - owned by `run-services`; upstream orchestration/composition DTOs
* `Chummer.Engine.Contracts` - engine provenance and semantic seed DTOs only

## 3.2 Hard package rule

`Chummer.Media.Contracts` must be dependency-light and **one-way consumable**.

It may be referenced by:

* `chummer6-media-factory`
* `chummer6-hub`
* `chummer6-mobile`
* `chummer6-ui`
* `chummer6-hub-registry`

It must not reference those repos back.

## 4. What belongs in `Chummer.Media.Contracts`

### 4.1 Asset primitives

* `MediaAssetId`
* `MediaAssetKind`
* `MediaArtifactRole`
* `MediaAssetHandle`
* `MediaAssetManifest`
* `MediaBinaryLocator`
* `MediaChecksum`
* `MediaDimensions`
* `MediaDuration`
* `MediaPreviewRef`

### 4.2 Job primitives

* `MediaRenderJobId`
* `MediaRenderJobKind`
* `MediaRenderJobState`
* `MediaRenderJobReceipt`
* `MediaRenderProgress`
* `MediaRenderFailure`
* `MediaProviderRun`
* `MediaLineageRef`
* `MediaRetryPolicy`

### 4.3 Lifecycle primitives

* `AssetApprovalState`
* `AssetRetentionState`
* `AssetRetentionPolicy`
* `AssetExpiryPolicy`
* `AssetPinState`
* `AssetReviewRecord`
* `AssetCanonicalSelection`
* `AssetSupersessionRecord`

### 4.4 Domain families

* `DocumentRenderContracts`
* `PortraitRenderContracts`
* `VideoRenderContracts`
* `ThumbnailContracts`
* `TemplateContracts`
* `StyleContracts`

## 5. What stays in `Chummer.Run.Contracts.Media`

`run-services` owns the "why" DTOs and the public business language.

Those contracts should contain:

* composition models assembled from campaign/session context
* approval workflow commands
* delivery/publish commands
* upstream draft/result summaries
* user-facing projection DTOs for GM/player surfaces

They should not contain:

* provider-run audit fields
* binary locators
* asset checksums
* render job attempt records
* internal queue state
* provider SDK-specific fields

## 6. Contract split by example

### Good upstream contract (run-services)

`NewsIssueComposition`

* campaign/session identifiers
* approved facts and tone profile
* sections and text blocks already drafted
* template/style refs
* delivery/approval hints

### Good downstream contract (media-factory)

`NewsIssueRenderPlan`

* composition payload normalized for rendering
* template version
* style pack version
* render target(s)
* preview policy
* retention policy
* idempotency metadata

### Good result contract (media-factory)

`NewsIssueRenderResult`

* job receipt
* generated asset manifests
* preview handles
* lineage refs
* structured warnings/failures

## 7. Current public contract correction

The currently visible `MediaContracts.cs` mixes:

* render requests/results
* delivery/publish results
* play/memory dependencies
* approval state
* campaign/session semantics

That file should be split into:

* `Chummer.Media.Contracts/*`
  pure render/job/asset/lifecycle families
* `Chummer.Run.Contracts.Media/*`
  upstream composition, publish, attach, and delivery families

## 8. Recommended namespace plan

```text
Chummer.Media.Contracts
  Assets/
  Jobs/
  Lifecycle/
  Templates/
  Documents/
  Portraits/
  Videos/
  Thumbnails/
  Common/

Chummer.Run.Contracts.Media
  Composition/
  Delivery/
  Approval/
  Projection/
  PublicationBridge/
```

## 9. Internal API surface

Media-factory should expose an internal API only.

Suggested route groups:

* `POST /api/media/jobs`
* `GET /api/media/jobs/{jobId}`
* `POST /api/media/jobs/{jobId}:cancel`
* `GET /api/media/assets/{assetId}`
* `POST /api/media/assets/{assetId}:pin`
* `POST /api/media/assets/{assetId}:supersede`
* `POST /api/media/callbacks/job-complete` (optional later)
* `GET /api/media/providers/health`

Clients do not call these routes directly.
Only `run-services` should.

## 10. Change process

Any change to `Chummer.Media.Contracts` must:

* update contract fixtures
* include package version notes
* state consumer impact across `run-services`, `play`, `presentation`, and `hub-registry`
* include replay/compatibility guidance if the change touches job or asset state
* avoid hidden source-copy mirrors

## 11. Exit criteria for the contract reset

The boundary/contract plane is correct when:

* `Chummer.Media.Contracts` builds in isolation
* no media DTO source copies remain in other repos
* `run-services` no longer needs play or memory namespaces to understand media execution
* presentation and play consume the package only, not mirrored source
* all public render results can be explained without referencing a campaign DB row
