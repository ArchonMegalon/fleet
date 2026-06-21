# Part 04 - Video pipeline

## 1. Purpose

The video pipeline handles the bounded video workloads that fit Chummer's product goals:

* route clips
* NPC video messages
* optional news/recap bulletins

It must stay intentionally constrained because video is the highest-cost and easiest-to-sprawl media domain.

## 2. Boundary

Upstream services prepare:

* script or narration text
* shot list or route points
* subject identity and visual references
* target audience and approval policy
* campaign/session linkage

Media-factory executes:

* render planning normalization
* preview-first flow
* provider job execution
* artifact persistence
* duration/size metadata capture
* retries and cost guards

## 3. Product families

### Route Cinema

Travel routes, exfil paths, smuggling runs, or movement summaries.
Inputs are structured route data, not raw maps to interpret.

### NPC Video Message

Short, controlled messages from recurring NPCs.
Inputs already contain approved script text and portrait/identity references.

### News Video

Optional in-universe bulletin or recap segment.
This should launch later than still-image and document outputs and must reuse the same preview/lifecycle substrate.

## 4. Component model

### `VideoRenderPlan`

The normalized plan for any video workload.
Includes script, shot list, reference assets, runtime caps, preview policy, and retention policy.

### `ShotListBundle`

A structured representation of scenes, beats, and required visual references.
This keeps upstream reasoning separate from downstream provider quirks.

### `VideoCostGuard`

Enforces hard limits:

* max duration
* max scenes
* max rerenders
* provider budget ceiling
* concurrency caps

### `RouteCinemaExecutor`

Executes map/route-derived plans.

### `NpcVideoExecutor`

Executes short character-message plans with portrait and voice references as applicable.

### `NewsVideoExecutor`

Optional extension for news/recap flows.

### `VideoPreviewGenerator`

Produces a cheap preview artifact whenever possible.

## 5. Preview-first strategy

Preview-first is mandatory unless the provider makes it impossible.
The normal path should be:

1. validate plan
2. generate poster frame / teaser / still preview
3. optionally require explicit confirmation upstream for expensive final render
4. execute full render
5. persist final artifact and manifests

This keeps costs bounded and avoids wasting full renders on obviously bad drafts.

## 6. Failure model

Video failures should classify clearly:

* invalid shot list
* missing anchor/reference
* provider capacity failure
* budget cap exceeded
* unsupported duration/scene count
* cancelled before final render
* output corrupted or incomplete

Every failure must leave a coherent receipt and provider-run record.

## 7. Contract hints

Suggested fields on `VideoRenderPlan`:

* `PlanKind`
* `SceneCount`
* `DurationBudgetSeconds`
* `PreviewFirst`
* `ReferenceAssetIds`
* `NarrationScript`
* `ShotList`
* `StylePackRef`
* `VoiceProfileRef`
* `SafetyProfile`
* `RetentionPolicy`
* `IdempotencyKey`

## 8. Tests

Video tests must prove:

* route and NPC video plans validate differently
* preview generation can succeed even when final render is disabled
* retry caps stop infinite rerenders
* cost guard blocks oversize jobs before provider spend
* manifests record duration and preview linkage
* cancelled jobs never publish final deliverable state
