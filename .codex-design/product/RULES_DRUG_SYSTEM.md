# Rule-system Drug and Pharmacology Model

## Scope

This document defines how character drug effects are represented, configured, and applied across Chummer rule systems.

Goal:

* make custom and generic drug use a first-class Build and Explain feature
* keep SR5 as the initial detailed profile
* support SR4 and SR6 through explicit profile seams
* make import and migration outcomes inspectable against current rules math

## Ownership split

`chummer6-core` owns deterministic pharmacology semantics.

`chummer6-ui` owns builder, apply workflow, and explanation presentation.

`chummer5a` and legacy file sources remain migration oracles.

Cross-repo truth for this lane lives in:

* `products/chummer/RULES_DRUG_SYSTEM.md` (design spec)
* `products/chummer/INTEROP_AND_PORTABILITY_MODEL.md` (migration receipts and import posture)
* `products/chummer/BUILD_LAB_PRODUCT_MODEL.md` (build-time integration)

## Canonical data model

`chummer6-core` MUST use one canonical pharmacology domain model with these entities:

* `DrugCatalogEntry`
  * source kind: native rule profile template, custom recipe, imported legacy entry
  * ruleset profile id
  * allowed vectors/routes (`oral`, `injection`, `inhalation`, `spray`, etc.)
  * optional stacking policy and conflict policy
  * optional category tags (`stim`, `resistance-breaker`, `condition`, etc.)
* `DrugComponent`
  * normalized atomic effect vector
  * strength and dose mapping
  * duration profile
  * interaction tags for compatibility filtering
* `DrugEffect`
  * target field (`body`, `reaction`, `agility`, `logic`, etc.)
  * operator (`add`, `set`, `min`, `max`, clamp)
  * gating conditions
  * failure class when context missing
* `DrugDosePlan`
  * dose amount + unit
  * timing model (instant, delayed, pulse)
  * application vector
  * optional quality/purity modifiers
  * optional administration context (`voluntary`, `forced`, `timed-release`, `re-dose`)
* `DrugRecipeDefinition`
  * canonical SR5 custom-drug recipe object
  * lists selected scaffold, ingredients, grade, vector, and legality envelope
  * records explicit ruleset profile and source references for every chosen slot
* `DrugRecipeSlot`
  * named construction seam such as chassis, delivery vector, potency band, onset model, duration model, crash model, addiction modifier, or requirement gate
  * constrains what can be combined and what scales with dose
* `DrugActiveState`
  * pending onset, active window, crash window, cooldown, expiry, removed
  * records the current reason a dose is still applying or has stopped
* `DrugReceipt`
  * request snapshot (`before` character stats)
  * profile resolution and formula pointers
  * computed `after` stats
  * diff matrix by field
  * expiry/stack state and blockers
  * proof of rule profile used
  * active-state transition trace
  * addiction and crash obligations due after application

## SR5-first profile contract

The initial required profile must be SR5.

The ruleset contract must include:

* explicit dose bands and side-effect curves
* clear duration model with stack decay and expiry
* legality/rule-boundary checks in the same contract
* a documented conflict matrix for overlapping effects
* explicit recipe-slot semantics for custom-drug construction

## SR5 custom-drug builder contract

SR5 must not treat custom drugs as opaque improvement bundles or one-off XML shortcuts.

The required design shape is:

1. Choose a scaffold or start from blank.
2. Choose route or vector.
3. Choose potency and dose band.
4. Choose onset and duration behavior.
5. Choose crash, addiction, and legality modifiers.
6. Resolve requirement gates, grade restrictions, and blocked combinations.
7. Preview the full effect receipt before creating a reusable catalog entry or applying a dose.

The custom-drug builder must be data-driven:

* rules profiles define available recipe slots and legal combinations
* UI does not hard-code SR5 formulas
* catalog drugs and custom drugs compile into the same canonical entities

The builder must also support named reusable recipes:

* favorite or saved recipe
* campaign-specific recipe
* imported legacy recipe with lossy-conversion notes

## Shared conditional-effect contract

Drug application must reuse the same conditional-effect activation semantics that power other situational modifiers.

That means:

* active drugs, foci, optical enhancements, sustained effects, and similar temporary states must all expose
  * current activation state
  * reason the effect applies
  * reason it is blocked or inactive
  * source-linked explanation
* UI may render different controls for different effect families, but they all consume one core activation and receipt model

This is required so SR5 drug application does not become another special-case modifier island.

SR4 and SR6 support must follow the same profile seam:

* no ad-hoc branching in UI
* no duplicate math in desktop/mobile/web layers
* no import-only interpretation shortcuts

## Custom and generic drug flow (UI semantics)

All drugs, custom or generic, share one UX and application engine:

1. Open pharmacology plane.
2. Select a catalog entry or build a recipe.
3. Tweak dose, vector, context, and optional activation assumptions.
4. Open projected results panel and source-linked explanation before commit.
5. Apply and receive an active-effect timeline entry with a `DrugReceipt`.
6. Show clear controls for expiry, stack cap, re-dose, suspend, and revert actions.

The same apply path MUST be used for:

* catalog drugs
* custom-built drugs
* imported legacy drugs

No special-case UI-only behavior may produce different stats changes from custom versus catalog flows.

## Pharmacology plane design

The UI shape for SR5 must feel like a real workbench, not a hidden modifier editor.

Required regions:

* `Catalog`
  * stock drugs
  * saved custom recipes
  * imported legacy recipes normalized into current terms
* `Lab`
  * recipe-slot editor for building or editing custom SR5 drugs
  * legality, conflict, and requirement warnings as the user edits
* `Preview`
  * before or after stat diff
  * effect timeline with onset, active window, and crash window
  * addiction and quality interactions due
  * source references
* `Active effects`
  * currently active doses
  * pending onset or crash entries
  * quick re-dose and clear actions

Quick-apply affordances are required:

* favorite dose presets
* one-click apply for common catalog entries
* one-click repeat of the most recent dose plan where rules allow it
* grouped cleanup for "remove expired" and "recompute active states"

## Convenience design requirements

The SR5 feature must feel convenient without hiding consequences:

* one click to add a common template (e.g. stimulants, healing aids)
* one-step dosage presets for common use cases
* clear warning when a drug is outside expected legality envelope
* grouped apply/undo for repeated doses
* timeline view that shows both numeric stat deltas and qualitative states
* direct comparison between profile variants before commit
* no orphaned qualities, improvements, or active states after removal
* quick access from the build surface, attribute rail, and active-effect rail without duplicating rules logic

## Migration and import posture

For chummer5a and heritage file imports:

* import should normalize legacy drug records into canonical `DrugCatalogEntry` and `DrugDosePlan` objects when present
* computed results are accepted as migration outputs only with a `DrugReceipt`
* `DrugReceipt` must include:
  * source fields detected from legacy
  * normalized interpretation
  * any lossy conversion notes
  * post-recompute validation status

If an import result claims a final attribute value:

* Chummer must re-run rule math from normalized base + ruleset profile
* discrepancies become explicit "needs review" rather than silent acceptance

If a legacy file describes drugs through opaque qualities or improvised improvements:

* import must lift those records into a canonical pharmacology interpretation when possible
* when exact reconstruction is impossible, the receipt must say so explicitly
* removal or expiry behavior must still be modeled through canonical active states rather than legacy residue

This becomes the basis for the future herolab and legacy corpus parity tests.

## Test architecture

Design requires three test bands:

### A. Rules-profile unit band

* deterministic profile application at canonical base states
* SR5 profile unit cases for edge-dose and stack behavior

### B. Builder behavior band

* custom recipe -> effect vector -> timeline diff preview
* catalog and custom path parity
* active-state add, re-dose, suspend, expire, and remove flows
* no orphaned qualities or modifier residue after removal

### C. Import parity band

* for each legacy fixture with drug outcome fields:
  * capture original final stats and relevant context
  * re-run with current rules profile in the same context
  * classify match/mismatch and capture deltas

Failure in band C opens a design/task follow-up with specific profile delta evidence.

## Exit criteria (design)

This lane is materially implemented in design when:

* model entities above are unambiguous and versioned by ruleset
* custom and generic flow is a single shared apply contract
* migration receipts are mandatory for legacy import paths
* import parity is codified as a required proof category for drug-bearing fixtures
