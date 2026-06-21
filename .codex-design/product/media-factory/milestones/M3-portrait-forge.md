# M3 - Portrait Forge split

## Goal

Move portrait execution fully into media-factory with safe lineage and canonicalization.

The deliverable is bigger than "images come back."
It is:

* variant sets
* reroll lineage
* review history
* canonical selection
* preview/thumbnail linkage
* retention-safe cleanup

## Included

* portrait render plans
* provider adapter
* portrait executor
* variant assembly
* identity/consistency store
* canonical selector
* review history persistence

## Excluded

* lore correctness judgments
* delivery/publish actions
* player-facing review UI
* general image studio behavior

## Detailed design

### 1. Portrait identity model

Introduce a stable identity grouping separate from any single asset.
A portrait identity represents "the visual continuity of this entity."
Asset drafts and canonicals live under that identity.

### 2. Reroll semantics

Rerolls are not replacement writes.
A reroll creates a new draft with:

* parent pointer
* root pointer
* depth
* reason
* provider run lineage

### 3. Canonical selection protocol

The selector should update lifecycle state only.
It does not move binaries.
It does not delete sibling variants.
It records:

* old canonical
* new canonical
* actor
* reason
* timestamp

### 4. Provider abstraction

The provider adapter must normalize:

* safety status
* credit/cost hint
* generated assets
* warnings
* retryability

The rest of the system should not care which vendor made the image.

### 5. Cleanup rules

Draft siblings are TTL-bound by default.
Canonical and pinned variants are retained per policy.
Previews follow parent lifecycle unless explicitly pinned.

## Exit tests

* portrait jobs produce multiple variants
* rerolls preserve lineage and root identity
* one canonical can be selected and later changed with history
* pinned canonical assets survive cleanup
* provider failure never leaves two canonicals active
