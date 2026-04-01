# Rule environment and amend system

## Purpose

Chummer needs a first-class rule-environment system, not ad hoc custom-data cargo.

This file defines the current-target product and contract posture for:

* source packs
* rules presets
* amend packages
* activation receipts
* portability and restore behavior

It preserves the useful shape of the Chummer5a amend system so the same package family can later be governed and promoted instead of re-invented.

## Product promise

Chummer must let a user, campaign, or group say:

* these are the source packs and optional rule packages that define what this build means
* this is the exact amend set that is active right now
* this is what changed when the package set changed
* this is why the current result is legal, blocked, or divergent under this environment
* this runner or campaign can be restored on another device without mystery package drift

Rule environments are therefore current product truth, not future-only governance scaffolding.

## Canonical terms

### `RuleEnvironment`

The versioned environment reference that a runner, campaign, or workspace restores against.

It carries:

* base ruleset identity
* source pack refs
* preset refs
* amend package refs
* option toggles
* compatibility fingerprint
* activation receipt refs
* owner scope and approval posture

### `RulesPreset`

A named package selector that activates a known combination of source packs, option toggles, and optional amend packages.

Presets are not magical aliases.
They must resolve to explicit package refs and fingerprints.

### `AmendPackage`

A versioned, checksummed package that changes catalog or language truth in a bounded, inspectable way.

An amend package may:

* replace a whole target file
* merge catalog fragments into a canonical target
* express selector-targeted patch operations against canonical content

### `ActivationReceipt`

The user-facing record of:

* what package graph was requested
* what compiled successfully
* what changed in effective content
* what was blocked, missing, downgraded, or lossy
* the compatibility fingerprint used for compute and portability

## Chummer5a continuity rule

Chummer6 must preserve the useful capabilities of the Chummer5a amend system in a safer, more productized form.

That means the current target must support the equivalent of:

* full-file replacement for bounded catalogs
* deterministic fragment merge into canonical catalogs
* selector-targeted add, replace, append, and remove behavior
* optional regex replace where legacy compatibility truly requires it
* add-if-not-found behavior when the package explicitly asks for it
* manifest, priority, and checksum validation

The current target does not need to preserve raw undocumented XML behavior as a user contract.
It does need to preserve the functional power that made Chummer5a amend packs useful.

## Canonical package modes

### `replace-file`

The package replaces a whole canonical target file.

Use this when:

* the source really is a full alternative catalog
* partial merge would be less trustworthy than replacement
* the replacement can be fingerprinted and explained clearly

### `merge-catalog`

The package contributes fragments into a known target catalog using deterministic precedence and canonical selectors.

Use this when:

* the package changes a subset of entries
* the user needs explainable diffs instead of opaque whole-file swaps
* later governed promotion should be able to reason about impact cleanly

### `legacy-amend-import`

The package started as Chummer5a-style custom data and is compiled into the canonical vNext amend graph.

This mode is required so legacy amend packs can become a migration and oracle lane instead of dead compatibility cargo.

## Canonical amend graph

`chummer6-core` must compile every active rule environment into one deterministic amend graph before rules compute begins.

The graph must normalize package inputs into:

* target catalog
* stable selector set
* operation kind
* payload
* add-if-not-found posture
* priority order
* source package provenance

Supported normalized operation kinds are:

* `add`
* `replace`
* `append`
* `remove`
* `regex_replace`

`recurse` is an implementation detail of legacy import, not a user-facing product term.

The engine must not compute against implicit filesystem precedence or ambient local files.

## Selector rule

Selectors must prefer stable ids and canonical named seams over freeform positional targeting.

Allowed selector ingredients:

* stable id
* canonical name
* bounded path within a known catalog schema
* explicit filter clauses when legacy compatibility requires them

Unbounded selector magic is forbidden as a product contract.
If a legacy amend pack depends on brittle targeting, the activation receipt must say so.

## Ownership split

### `chummer6-core`

Owns:

* amend package compilation
* package graph resolution
* checksum and manifest validation
* compatibility fingerprints
* activation receipts
* explainable impact summaries
* legacy amend-pack import and loss classification

### `chummer6-ui`

Owns:

* rule-environment selection and inspection surfaces
* preset picker and active-environment badges
* amend-package preview and diff UX
* activation, rollback, and mismatch recovery UX
* explicit warnings when a runner or campaign needs packages that are not active locally

### `chummer6-hub`

Owns:

* person, campaign, and group rule-environment refs
* governed sharing and restore orchestration
* portability-safe activation and mismatch messaging

### `chummer6-hub-registry`

Owns immutable package and compatibility metadata when amend packages or governed rule packs are published.

### `chummer6-design`

Owns the current-target product promise, vocabulary, exit criteria, and future reuse discipline.

## Current-target UX shape

The flagship product needs one obvious rule-environment surface.

Required regions:

* `Environment`
  * active ruleset
  * source packs
  * presets
  * amend packages
  * compatibility fingerprint
* `Preview`
  * before/after package diff summary
  * impacted catalogs and entry counts
  * blocked or conflicting operations
  * missing-package and downgrade warnings
* `Explain`
  * package provenance
  * why this selector matched
  * why a package changed this outcome
* `Restore`
  * what this runner or campaign expects
  * what this device has
  * the next safe action

The product must not scatter these answers across hidden settings panels, startup flags, and operator folklore.

## Build and explain rule

Build, inspect, compare, explain, import, and restore flows must all expose the same active rule-environment truth.

That means:

* Build Lab previews use the compiled amend graph, not UI-local guesses
* explain receipts cite the active environment fingerprint
* imports classify missing or lossy amend-package carryover explicitly
* restore and cross-device flows say when a package mismatch would change compute

## Portability and restore rule

Runner and campaign portability must preserve:

* active rule-environment refs
* package fingerprints
* amend package refs
* activation receipt refs
* compatibility posture for the destination surface

The user must never have to guess whether a runner loaded under the same effective package graph.

## Flagship-grade bar

The current target is not flagship grade until:

* the active ruleset, preset, and amend package set are always visible on build and explain surfaces
* package activation can be previewed before commit with clear diffs and conflict warnings
* restore, import, and portability flows expose missing or incompatible packages before wrong compute happens
* Chummer5a-style amend packs can either compile into the canonical amend graph or emit explicit lossy/blocking receipts
* the same amend package family can later be governed and promoted without inventing a second representation for Karma Forge

## Non-goals

* ambient folder magic as the primary product experience
* a second rules engine inside the UI
* irreversible package activation without receipt or rollback path
* future-only governance abstractions with no current user-facing value
