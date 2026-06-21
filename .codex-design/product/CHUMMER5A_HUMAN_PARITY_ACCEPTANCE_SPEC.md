# Chummer5A Human Parity Acceptance Spec

## Purpose

This is the release-blocking human-tester canon for the remaining hard Chummer5A parity families.

It exists because broad readiness or family-level parity prose is not enough.
If a veteran tester can still say "this dialog feels missing, buried, slower, or behaviorally wrong," then the product is not yet at human-feeling parity even if aggregate gates are green.

This spec defines:

* which sub-workflows are still judged as release-blocking
* which dialogs or utility surfaces must be proven directly
* what a human tester is allowed to accept as modernization
* what a Chummer6-only control must justify to stay
* what every parity audit must list for every UI element on those surfaces

The machine-readable companion for this canon is `CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml`.

## Core rule

For the families below, parity is not closed until Chummer6 produces direct screenshot-backed and runtime-backed evidence for the exact dialog or utility route a veteran user would judge.

No gate may collapse these families into a generic "desktop parity" or "flagship readiness" pass.

## Required audit output

Every audited dialog in this spec must emit an element inventory with these fields:

* `family_id`
* `surface_id`
* `dialog_id`
* `element_id`
* `element_label`
* `present_in_chummer5a` as `yes` or `no`
* `present_in_chummer6` as `yes` or `no`
* `visual_parity` as `yes` or `no`
* `behavioral_parity` as `yes` or `no`
* `removable_if_not_in_chummer5a` as `yes` or `no`
* `reason`

If any required field is missing, the dialog stays open.

## Human tester rules

### 1. Default parity stance

If a control or sub-workflow exists in Chummer5A and still serves a real user job, the default expectation is:

* `visual_parity = yes`
* `behavioral_parity = yes`

unless this spec explicitly grants a bounded modernization exception.

### 2. Allowed modernization

Modernization is allowed when it improves density, readability, or continuity without weakening:

* first-step discoverability
* workbench directness
* state visibility
* operator speed
* trusted completion of the same user job

Allowed modernization maps to the divergence class `may_improve`.

### 3. Disallowed modernization

Modernization fails parity if it:

* buries a formerly first-class dialog behind dashboard indirection
* moves a dense workflow into a slower ritual path
* hides actionable state behind generic "review" or "overview" framing
* makes source, import, or export truth harder to inspect
* converts a direct utility into a sidecar or post-hoc explanation-only surface

If a surface trips any of these conditions, it is a `must_match` failure until the replacement route proves equal or better directness, speed, and trust.

### 4. Chummer6-only extras

A Chummer6-only control may stay only if it does at least one of these:

* shortens the path to a legacy user job
* increases trust or explainability without adding indirection
* improves continuity between install, live play, recap, and return moments

Otherwise it should be marked `removable_if_not_in_chummer5a = yes`.

This is the divergence class `may_remove_if_non_degrading`.

### 5. Collapsed modern surfaces

If several Chummer5A dialogs are merged into one Chummer6 surface, the audit must still enumerate every legacy job and every visible control that carries it.

One modern shell cannot claim parity by hiding the old control inventory inside a generic "covered" family label.

## Release-blocking family matrix

### Family `translator_xml_bridge`

**Why it is release-blocking:** veteran users still expect first-class access to translator tooling, XML amendment posture, and custom-data bridge truth.

| Surface | Must remain first-class | Allowed modernization | Disallowed drift | Chummer6-only extras |
| --- | --- | --- | --- | --- |
| `translator_dialog` | translator title, language inventory, overlay or corpus posture, search or filter, direct bridge handoff | modern layout, chips, drawers, side panes | bury translator route inside generic settings or dashboard flow | provenance chips may stay if they do not hide language inventory |
| `xml_amendment_editor` | amendment scope, file or overlay target, change visibility, save/apply posture | richer diff view, validation badges, grouped navigation | bridge that only describes XML posture without a real amendment route | validation hints may stay if they shorten safe authoring |
| `custom_data_bridge` | explicit custom-data route, enabled overlay visibility, governed or stale posture, bridge to translator or amendment lane | unified bridge shell, source-backed posture badges | custom-data only visible as abstract receipt or health text | overlay counts and provenance drawers may stay if they remain first-surface |

**Required screenshots:**

* translator route opened with live language inventory visible
* translator route with one selected language or overlay state
* XML amendment route opened with editable target visible
* custom-data bridge opened with enabled overlay posture visible

### Family `dense_builder_and_career`

**Why it is release-blocking:** this is where veterans feel speed loss immediately.

| Surface | Must remain first-class | Allowed modernization | Disallowed drift | Chummer6-only extras |
| --- | --- | --- | --- | --- |
| `attributes_workspace` | direct attribute editing, current totals, spend or consequence visibility, no fake review framing | denser cards, modern grouping, improved badges | attribute work hidden behind summary-only shell or delayed edit mode | explain chips may stay if editing stays immediate |
| `skills_workspace` | searchable skill list, rating state, category grouping, direct edit posture | better filtering, staged explain affordances | skills hidden behind document-style review or deep drilldown only | source-backed hints may stay |
| `qualities_workspace` | add/remove flow, active quality list, validation posture, source anchor visibility | grouped panels, explain drawer | quality management downgraded to passive list plus separate wizard | provenance badges may stay |
| `gear_and_augment_workspace` | dense list, affordability or legality posture, equip/manage flow, direct compare posture | better cards, compare side pane, improved filters | workflow broken into too many serial pages | compare aids may stay |
| `magic_matrix_vehicle_tabs` | ruleset-specific dense work surface with direct state editing | better segmentation and help posture | one-size-fits-all shell that weakens expert speed | helper panels may stay if optional |

**Required screenshots:**

* new character in attributes
* live career workspace in skills
* qualities management visible
* gear or augment dense management surface visible
* one ruleset-specific specialist tab visible

### Family `dice_initiative_and_table_utilities`

**Why it is release-blocking:** table-time trust depends on quick utilities.

| Surface | Must remain first-class | Allowed modernization | Disallowed drift | Chummer6-only extras |
| --- | --- | --- | --- | --- |
| `dice_roller` | direct dice input, result visibility, repeatable roll posture | cleaner controls, richer receipts | hidden behind generic debug or explain tool | explanation panel may stay if result remains immediate |
| `initiative_utility` | initiative calculation, pass or order preview, roster context | improved context chips, grouped controls | initiative only implied indirectly from character sheet | planning aids may stay |
| `table_utility_surface` | quick utility access without campaign detour | utility tray or compact dashboard section | dashboard ritual required before rolling or tracking | utility history may stay if compact |

**Required screenshots:**

* dice roller open with result state
* initiative utility open with roster context
* quick utility entry point visible from flagship desktop shell

### Family `identity_contacts_lifestyles_history`

**Why it is release-blocking:** these dialogs carry continuity and campaign memory.

| Surface | Must remain first-class | Allowed modernization | Disallowed drift | Chummer6-only extras |
| --- | --- | --- | --- | --- |
| `identity_and_licenses` | SIN, license, and identity posture visible and editable | better grouping and warnings | identity buried inside abstract dossier summary only | trust badges may stay |
| `contacts_dialog` | contacts list, relationship or role fields, direct add/edit posture | richer chips, tags, sorting | contacts flattened into read-only recap view | context chips may stay |
| `lifestyles_dialog` | lifestyle entries, costs or durations, direct edit posture | cleaner grouping, scenario badges | lifestyle management reduced to secondary notes | explain aids may stay |
| `history_or_journal` | visible event or change history, continuity memory, direct review posture | better filtering and consequence framing | history only available through exported artifacts or support packets | continuity chips may stay |

**Required screenshots:**

* identities/licenses route
* contacts dialog
* lifestyles dialog
* history or journal continuity route

### Family `legacy_and_adjacent_import_oracles`

**Why it is release-blocking:** migration trust is not real if oracle coverage is implicit.

| Surface | Must remain first-class | Allowed modernization | Disallowed drift | Chummer6-only extras |
| --- | --- | --- | --- | --- |
| `hero_lab_import` | direct Hero Lab import entry point, file or bundle target, import verdict visibility | richer receipts and repair hints | import oracle only referenced in docs or receipts, not reachable in UI | repair hints may stay |
| `legacy_import_matrix` | explicit Chummer4/5a and adjacent SR6 oracle posture | consolidated import center, better certification badges | old and adjacent oracles reduced to abstract certification prose | oracle coverage chips may stay |
| `migration_confidence_review` | bounded loss, manual review, and provenance visible on first review surface | richer diff or explain views | migration claims green without surfaced caveats | detailed explain drawers may stay |

**Required screenshots:**

* Hero Lab import route
* legacy import oracles matrix
* migration confidence review with bounded-loss or provenance posture

### Family `sheet_export_print_viewer_exchange`

**Why it is release-blocking:** print/export/viewer flows are still part of serious completion.

| Surface | Must remain first-class | Allowed modernization | Disallowed drift | Chummer6-only extras |
| --- | --- | --- | --- | --- |
| `sheet_viewer` | visible sheet preview route, chosen sheet posture, first-class review surface | richer preview shell | preview hidden behind export-only action | preview aids may stay |
| `print_multiple` | multi-runner print posture, target selection, print readiness | better batching UI | print only possible by one-runner export workaround | batch badges may stay |
| `export_exchange` | explicit PDF, JSON, Foundry, and related exchange targets | grouped export center, richer manifest info | exchange posture only implied in Build Lab prose | compatibility badges may stay |

**Required screenshots:**

* sheet viewer
* multi-runner print route
* export/exchange route with multiple first-class targets visible

### Family `sr6_supplements_designers_house_rules`

**Why it is release-blocking:** adjacent SR6 power users still judge supplement and authoring posture.

| Surface | Must remain first-class | Allowed modernization | Disallowed drift | Chummer6-only extras |
| --- | --- | --- | --- | --- |
| `supplement_posture` | supplement coverage visibility and selection posture | clearer catalog and coverage chips | supplement truth only visible in docs or hidden receipts | coverage badges may stay |
| `designer_tools_catalog` | explicit designer-tool posture for spell, vehicle, cyberdeck, drug, quality, and similar families | modern catalog shell | designer posture only described as future/adjacent with no surfaced route | tool-family chips may stay |
| `house_rule_overlay` | visible house-rule posture, overlay counts, activation truth | improved grouping and warnings | house-rule truth hidden behind opaque settings or backend-only overlays | safety badges may stay |

**Required screenshots:**

* supplement posture visible
* designer tools catalog visible
* house-rule overlay posture visible

## Gate requirement

For every family above, the gate stack must fail closed when any of these are missing or stale:

* required screenshots
* required runtime receipt for opening the route
* required per-element inventory rows
* explicit reason for any `visual_parity = no` or `behavioral_parity = no`
* explicit reason for any Chummer6-only control that is not removable

The gate stack should consume `CHUMMER5A_HUMAN_PARITY_ACCEPTANCE_MATRIX.yaml` for the field list, family ids, surface ids, required screenshots, and milestone mapping instead of re-encoding that shape ad hoc.

## Product rule

The point of this spec is not clone worship.

The point is to make sure Chummer6 earns the same trust a serious Chummer5A user would extend to a mature work surface:

* direct
* dense
* inspectable
* fast
* honest about what differs
* honest about what can be removed
* durable across install, update, restore, and migration
* explainable when a computed value or import result is disputed
