# Horizon Promotion Rules

## Purpose

This file is the human-readable companion to `HORIZON_REGISTRY.yaml`.
It exists so future lanes cannot be narrated like shipment promises while flagship truth is still contingent.

## Rules

* A horizon is not a shipment claim.
* A horizon may be public, exciting, and media-safe while still being contingent.
* Public-guide inclusion is not the same thing as flagship scope.
* A horizon cannot outrun current blocker, release, or owner-handoff truth.

## Promotion ladder

### 1. `horizon`

The lane is real canon and may be publicly described.
It is still future-facing.

### 2. `shipped_mvp`

Some executable lane exists, but the lane is still bounded.
It must not borrow flagship claims from adjacent product surfaces.

### 3. intermediate bounded state

The lane has deeper product behavior, but owner handoff, proof, or release posture is still incomplete.

### 4. flagship-adjacent promotion

Allowed only when:

* `build_path.current_state` has advanced beyond `horizon`
* `owner_handoff_gate` is materially satisfied
* owning repos can cite executable proof
* public/support/release wording no longer reads as contingent

### 5. flagship scope

Allowed only when the lane satisfies `FLAGSHIP_RELEASE_ACCEPTANCE.yaml` for the user promises it exposes.

## Forbidden shortcuts

Do not:

* describe a horizon as near-term shipment because the doc is polished
* describe a horizon as flagship because a public route or media packet exists
* let horizons outrun open red blockers or lived-system release truth
* let one repo's proof stand in for cross-repo owner handoff

## Source of truth

`HORIZON_REGISTRY.yaml` remains the machine-readable authority.
This file explains how to read and narrate that authority.
