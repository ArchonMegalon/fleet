# ADR-0015: Drug systems are deterministic, ruleset-pluggable, and receipt-backed

Date: 2026-03-31

Status: accepted

## Context

Character drug effects in Shadowrun rulesets are currently treated as ad hoc feature behavior instead of a named, deterministic subsystem.

That creates two risks:

* custom and generic drug usage are implemented differently across surfaces, and outcomes are hard to compare
* SR5 detail can drift from SR4/SR6 behavior without an explicit ruleset seam, while import/migration receipts do not preserve enough drug-level evidence

## Decision

Chummer now treats drug usage as a first-class pharmacology subsystem owned by the same engine boundary as other rules math.

The canonical owner and package path is:

* `chummer6-core` through `Chummer.Engine.Contracts`

The owning contracts and behavior split is:

* `chummer6-core` owns:
  * drug templates, custom compositions, and effect resolution
  * dosing, duration, cooldown, and conflict semantics
  * active-effect state transitions
  * deterministic before/after receipts for drug application
  * legacy and file-import normalization needed for migration
* `chummer6-ui` owns:
  * drug catalog/builder and application surfaces
  * per-ruleset convenience UX (especially SR5) around dosage and vectors
  * active-effect timeline display and user override affordances
  * preview before apply and warning flows from core receipts
* `chummer5a` remains a reference oracle for migration fixtures and regression examples

Ruleset behavior must be delivered as profile modules rather than hard-coded branching:

* one core domain model for drug lifecycle
* one profile contract per ruleset family (initially SR5, then SR4/SR6)
* explainability and receipts must point to the same profile identifier every time

## Consequences

### Positive

* drug application becomes deterministic and inspectable, with one source of truth in core
* custom and generic drugs share a single apply/lifecycle model
* SR4 and SR6 can be introduced through profile modules, without cloning the engine
* migration/import tests can compare legacy final stats against core-calculated replays through receipts

### Negative

* several data loaders must now emit normalized drug receipts instead of opaque modifiers
* existing surface behavior may change if legacy UI special-cases are not mapped into the new core domain first

## Design implications

1. Core must own a deterministic pharmacology domain model with:
   * drug template
   * drug component
   * effect expression
   * dose vector
   * active-instance lifecycle
   * profile-specific validation
2. Drug application flow must emit an explain receipt showing:
   * baseline values
   * chosen dose/vector
   * resolved effect expressions
   * resulting value diffs
   * active timers and expected expiry
3. UI must consume receipts for warning, preview, and rollback-like undo semantics.

## Explicit rejection

The following are rejected:

* calculating drug effects directly in UI without core contract-backed receipts
* shipping one hard-coded SR5 drug rule path with no SR4/SR6 profile seam
* treating legacy import effects as accepted just because they are in the source file
