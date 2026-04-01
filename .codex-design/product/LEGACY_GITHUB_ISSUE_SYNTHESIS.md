# Legacy GitHub Issue Synthesis

Date: 2026-03-31

## Purpose

This document records which legacy GitHub issue themes are still valid inputs into Chummer6 design, which ones matter for the flagship product, and which ones should stay parked.

It is not a promise to reproduce every legacy UX quirk.
It is the canon for turning legacy issue pressure into current product truth.

## Corpus audited

### Chummer5A

Official GitHub issue tracker audited:

* `chummer5a/chummer5a`

Snapshot used for this synthesis:

* 4,219 issues
* 90 open
* 4,129 closed

Observed pressure clusters in the corpus:

* UI and explain friction
* crash and cancellation reliability
* qualities, house rules, and conditional modifiers
* gear grouping, locations, bundles, and PACK behavior
* custom-data and settings-package consistency
* calendar and in-game date handling
* drugs and custom pharmacology behavior
* reputation/index tracking

### Chummer4

GitHub repo checked:

* `katiestapleton/chummer4`

Result:

* GitHub issues are disabled on the repo
* no repo-local GitHub issue corpus exists to sweep

Implication:

* SR4 design inputs come from rules canon, save/import fixtures, and repo behavior
* they do not come from a GitHub issue backlog in the same way Chummer5A does

## Triage rule

Legacy issues are pulled into Chummer6 canon only if they strengthen one or more flagship promises:

* deterministic build and explain truth
* fast, trustworthy character-building ergonomics
* receipts and provenance instead of hidden state
* transaction-safe editing with clear undo or recovery posture
* clean ruleset seams for SR4, SR5, and SR6
* import and migration confidence

Issues are not canonized just because they are old, loud, or popular.

## Accepted design deltas

### 1. Conditional-effect controls must be first-class

Validated by recurring issue pressure around toggles, situational math, and hidden always-on modifiers.

Representative issues:

* `#5258` enable toggles for foci and similar conditional bonuses
* `#4745` explain damage-value components on hover
* `#3671` attach notes to attribute and skill-group context
* `#5222` spellcasting-focus misapplication illustrates why conditional scope must be explicit

Accepted canon:

* Chummer6 must have one receipt-backed conditional-effect system for situational bonuses and penalties.
* Foci, optical enhancements, sustained effects, drug effects, temporary buffs, and similar mechanics must all use the same activation or applicability contract.
* Explain surfaces must show why a conditional effect is active, inactive, blocked, or out of scope.

### 2. SR5 pharmacology needs both a catalog and a custom builder

Validated by direct drug-related requests plus recurring custom-effect breakage.

Representative issues:

* `#5253` grade and requirement gating for ware and drug systems
* `#5148` request for `drugs.xml` and reusable named drug groups
* `#4181` custom drugs can leave orphaned qualities behind after removal
* historical drug tickets such as `#773` and `#451`

Accepted canon:

* Chummer6 must not model drugs as opaque improvement bundles.
* SR5 must ship a real pharmacology subsystem with:
  * catalog drugs
  * custom-built drugs
  * deterministic application receipts
  * correct removal and expiry semantics
  * requirement, legality, and quality interactions owned by the rules engine

### 3. Grouping and organization matter for builder trust

Validated by repeated requests to organize qualities, notes, and gear context instead of forcing flat lists.

Representative issues:

* `#5257` group qualities and preserve grouping in print or export
* `#3671` notes on attributes and skill groups
* `#3304` expand usage of locations
* `#1000` separate gear by identities

Accepted canon:

* Chummer6 must treat grouping, location, and organizational metadata as first-class presentation state.
* Qualities, active effects, gear, and dossier annotations must support grouping or facet organization without changing rules truth.
* Print and export surfaces should preserve meaningful group structure where it helps human review.

### 4. Settings and custom-data packages need a cleaner contract

Validated by recurring requests for custom-data overrides, rules presets, and settings drift fixes.

Representative issues:

* `#5256` select a specific skill or skillgroup in karma-cost adjustments
* `#5255` build preset should auto-load required custom data
* `#5243` settings editor drift versus the saved XML
* `#4932` custom-data language-string overrides
* `#2211` gear-definition update behavior

Accepted canon:

* Chummer6 must model rules presets and optional overlays as explicit packages with dependencies, selectors, and proof of activation.
* A preset that requires an overlay must load or declare that dependency explicitly.
* UI preview state, saved state, and engine state must not disagree about what package set is active.
* Current canonical home: `RULE_ENVIRONMENT_AND_AMEND_SYSTEM.md`.

### 5. Calendar and in-game time need to be part of the character lifecycle

Validated by long-running requests around in-game dates, training completion, ordering, and expense semantics.

Representative issues:

* `#5259` change starting date crash
* `#5205` date adjustment in settings file
* `#4709` training-time planner on the calendar
* `#2066`, `#1456`, `#1801` richer in-game timeline fields and ordering

Accepted canon:

* Chummer6 must treat calendar and in-game time as character-lifecycle data, not as a printing afterthought.
* Training, downtime, expense timing, acquisition timing, and mission chronology must share one timeline model.
* Calendar mutation must be transaction-safe and crash-safe.

### 6. Bundles and PACK-like flows must be staged transactions

Validated by crash reports and post-chargen bundle friction.

Representative issues:

* `#5238` crash when cancelling out of adding a PACK
* `#5063` request for post-chargen PACK behavior
* historical PACK tickets `#203` and `#129`

Accepted canon:

* Bundle application must preview changes first, then apply atomically.
* Cancel must be safe.
* Partial side effects and orphaned improvements are design bugs, not acceptable legacy behavior.
* Chummer6 may support curated starter bundles after chargen, but only through the same transaction and explain model as any other acquisition flow.

### 7. Reputation and index ledgers should be explicit, not hacked through adjacent counters

Validated by repeated requests to support negative adjustments and index-to-reputation tracking.

Representative issues:

* `#5241` negative Street Cred and similar counters
* `#5240` Spirit Index and Wild Index support
* `#4558` historical negative Street Cred request
* `#4042` historical Astral/Wild Index request

Accepted canon:

* Character reputation state must be modeled as a small ledger with typed counters and typed spends, not only as unstructured non-negative integers.
* Derived thresholds such as index-to-reputation conversions must be visible and explainable.

### 8. Crash-safe cancellation and edit rollback are part of the product bar

Validated by the size of the crash-heavy corpus and the types of bugs still recurring in mature Chummer5A builds.

Representative issues:

* `#5238` PACK cancel crash
* `#5237` xpath-mode search crash
* `#5044` quality-prompt cancel leaves incorrect character state
* `#4791` reliance on message-pump hacks and deadlock risk

Accepted canon:

* Any modal or multistep builder flow must be modeled as a staged mutation with explicit commit or cancel semantics.
* Cancel must never leave the character in a half-mutated state.
* Crash recovery and diagnostics are product features, not just debug tools.

## Parked or rejected themes

These requests may be reasonable legacy asks, but they do not currently become flagship Chummer6 canon:

* direct Discord or Roll20 dicebot integration (`#3764`)
* arbitrary gear-image attachment as a core product promise (`#2047`)
* legacy-plugin-style extension behavior that bypasses deterministic contracts

They can be revisited later only if they fit the publication, artifact, or companion-surface story without weakening core truth.

## Canon changes mandated by this synthesis

This synthesis requires Chummer6 design to keep these seams explicit:

* one conditional-effect activation model
* one pharmacology model with SR5 custom-drug builder support
* one staged bundle application model
* one timeline model for calendar, downtime, and timed effects
* one package/overlay dependency model for settings and custom data
* one typed reputation/index ledger

If implementation work in Core or UI tries to solve one of these pressures ad hoc, the implementation is below design bar.
