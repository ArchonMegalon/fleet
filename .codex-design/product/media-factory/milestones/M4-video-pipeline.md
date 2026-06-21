# M4 - Video pipeline split

## Goal

Add controlled video execution for the bounded Chummer use cases that justify the cost.

This is the highest-risk milestone and should land only after the kernel, documents, and portraits are already solid.

## Included

* video render plans
* shot list bundle
* route video executor
* NPC message video executor
* optional news video executor
* preview-first flow
* cost guard and retry cap
* duration/scene metadata capture

## Excluded

* unlimited freeform video generation
* arbitrary user prompt playgrounds
* direct delivery policy
* unbounded long-form recap filmmaking

## Detailed design

### 1. Plan normalization

Every video job must be normalized before execution:

* kind
* script
* shot list
* refs
* expected duration
* preview requirement
* retry cap
* provider constraints

### 2. Cost control

Video jobs must be rejected before provider spend when they violate:

* scene count cap
* duration cap
* missing refs
* concurrent-budget cap
* forbidden style/provider combination

### 3. Preview-first protocol

The default lifecycle:

* preview created
* upstream review/approval optionally occurs
* full render starts only when allowed
* final video supersedes preview as primary asset, but preview remains linked

### 4. Cancellation

Cancellation must be meaningful.
If the provider supports cancel, call it.
If not, mark the job cancelled locally and ignore late provider completion except for safe cleanup/tombstoning.

## Exit tests

* route and NPC video plans validate independently
* cost guard blocks oversize jobs
* preview-first flow works
* cancelled jobs do not become published finals
* manifests capture duration and preview linkage
* provider outages become structured failures with lineage preserved
