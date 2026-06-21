# Part 03 - Portrait Forge

## 1. Purpose

Portrait Forge turns a grounded character or NPC identity package into bounded portrait variants with lineage, review history, and canonical selection.

This is not "freeform image magic."
It is a controlled image-production pipeline for Chummer entities.

## 2. Boundary

Upstream services own:

* the semantic identity of the subject
* the aesthetic digest
* spoiler/approval rules
* whether an undercover, damaged, or wanted-poster variant is needed

Media-factory owns:

* the render execution
* variant set assembly
* reroll lineage
* preview/thumbnail generation
* canonical selection bookkeeping
* retention and cleanup

## 3. Inputs

Good inputs:

* entity id and portrait identity id
* stable subject descriptor
* approved anchor images when available
* style pack or style family ref
* variant set request
* render constraints (resolution, count, safety class)
* retention policy

Bad inputs:

* "make this look cooler"
* lore judgment about whether the face is correct
* campaign truth changes
* player delivery instructions

## 4. Component model

### `PortraitRenderPlan`

Normalized execution input containing variant requirements, style refs, anchors, and lineage refs.

### `PortraitProviderAdapter`

Wraps the underlying image provider(s) and normalizes results.

### `PortraitForgeExecutor`

Runs the plan, produces variant assets, and stores receipts and provider runs.

### `PortraitVariantAssembler`

Groups rendered outputs into a draft set and creates preview handles.

### `PortraitConsistencyStore`

Tracks identity-level continuity data: style tokens, selected canonical portrait, prior variants, and reroll roots.

### `CanonicalPortraitSelector`

Applies review-driven canonical selection and supersession records.

## 5. Variant model

Supported variant intent should be explicit and enumerable:

* canonical/dossier headshot
* undercover variant
* damaged/post-run variant
* wanted-poster variant
* message/video portrait still
* thumbnail/preview derivative

Avoid "miscellaneous variant" until there is a concrete product need.

## 6. Lineage model

Portrait generation must preserve lineage because image generation is not deterministic.

Required fields:

* `PortraitDraftId`
* `PortraitIdentityId`
* `RootPortraitId`
* `ParentPortraitId`
* `RerollDepth`
* `PromptLineageRef`
* `StyleToken`
* `CanonicalGroupId`

This lets reviewers answer:

* what changed?
* what was rerolled?
* which one became canonical?
* which drafts may expire safely?

## 7. Canonicalization

Canonicalization is a lifecycle state transition, not a file replacement.

Rules:

* selecting canonical never deletes sibling variants
* rerolls create new siblings or descendants
* pinned canonical portraits outlive draft siblings by default
* canonical selection should be reversible with review history preserved

## 8. Content safety and moderation

This repo should not own global moderation policy, but it must expose safety hooks:

* content-safety status
* provider safety warning code
* blocked/unsafe output classification
* redaction/takedown lifecycle states when commanded upstream

## 9. Tests

Portrait tests must prove:

* multiple variants are returned in one draft set
* lineage survives rerolls
* canonical selection can move across siblings
* pinned canonical assets survive cleanup
* preview assets are linked and discoverable
* provider failures preserve review history and do not create phantom canonical assets
