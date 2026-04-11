# Surface design system and AI review loop

## Purpose

This file defines the shared design contract for every user-facing Chummer surface.

It exists so "make it nicer" does not turn into random local taste or generic admin-shell drift.
The goal is one authored product language that adapts correctly to desktop workbench, mobile/play, Hub, support, downloads, and public front-door surfaces.

`chummer6-design` owns this canon.
`chummer6-ui-kit` owns the reusable implementation substrate that makes it practical.

## Applies to

This contract applies to:

* desktop workbench and installer/update surfaces
* live play and mobile shell surfaces
* Hub account, support, community, and operator-adjacent surfaces
* public landing, downloads, help, and guide surfaces
* artifact preview, publication, and recap surfaces

It does not require the same layout everywhere.
It requires the same design language, trust posture, information hierarchy discipline, and quality bar everywhere.

## Core rule

Every promoted surface must feel intentionally designed, not merely assembled.

That means:

* one obvious primary path for the current job
* strong information hierarchy
* predictable command placement
* visible state and recovery posture
* calm chrome around dense data
* dark and light themes that remain legible and deliberate
* platform-respectful behavior instead of lowest-common-denominator layout reuse

## Cross-surface invariants

Every surface must preserve these rules:

### 1. Primary-path clarity

The main action for the current screen must be obvious.
Secondary and destructive actions may exist, but they must not visually compete with the main path.

### 2. Authored density

Chummer is a power-user product, but density must feel organized.

Required:

* grouped information instead of long flat walls
* scan-friendly labels and values
* stable placement for commands and critical state
* progressive disclosure for advanced detail instead of hiding the main workflow

### 3. Explicit state

Users must always be able to see:

* selection and focus
* stale, offline, pending, error, and warning state
* active ruleset and rule-environment posture where it materially affects trust
* active temporary effects, drugs, modifiers, and timing posture where they matter

### 4. High-trust theming

Light and dark variants must both be first-class.

Required token families:

* background
* base surface
* elevated surface
* accent surface
* border
* border strong
* text primary
* text secondary
* text inverse
* focus ring
* selection
* success
* warning
* danger
* info

No promoted surface may ship with accidental contrast combinations such as light text on light backgrounds, background-matched controls, or focus states that disappear in dark mode.

### 5. Keyboard and pointer parity

Promoted flows must be usable with both keyboard and pointer.

Required:

* visible focus
* stable tab order
* keyboard access to primary actions
* no hover-only essential affordances
* no pointer-only recovery path for blocked or errored state

### 6. Recovery is part of the design

Error, empty, blocked, preview, and conflict states must be designed intentionally.
A blank placeholder or framework-default error card is not flagship behavior.

## Layout grammars by surface

### Desktop workbench grammar

Desktop workbench surfaces default to:

* left navigation or workspace rail
* top title/command/search bar
* central task canvas
* optional right detail/inspector panel
* dense-data panels that preserve alignment and keyboard travel

The desktop workbench should feel like a serious instrument, not a settings website.

For Chummer specifically, the promoted desktop shell also preserves the legacy familiarity bridge in `CHUMMER5A_FAMILIARITY_BRIDGE.md`.

Desktop install and first-run grammar must read like one product:

* guided installer or in-app recovery first
* no browser to copy a claim code manually
* workbench-first continuation instead of dashboard, landing, or mainframe detours

Required Chummer desktop cues:

* a real desktop menu instead of web-style top navigation
* an immediate quick-action toolstrip directly beneath it
* dense left-and-center builder posture instead of a hero-led dashboard
* a compact bottom status strip that keeps trust metrics visible
* navigation rhythm that still feels recognizably like Chummer5a even after visual modernization

### Mobile and live-play grammar

Mobile and play surfaces must feel authored for live use:

* fewer simultaneous panels
* larger interaction targets
* crisp live/stale/offline/conflict indicators
* session-safe continuity cues
* short action ladders under pressure

They must not read like shrunk workbench screens.

### Hub and public-surface grammar

Hub, downloads, guides, and support surfaces must optimize for clarity, trust, and relationship continuity:

* calm visual rhythm
* bounded CTAs
* visible status and support truth
* polished, low-friction account handoff

They must not read like a generic admin console or a vague marketing splash page.

### Artifact and recap grammar

Artifact, dossier, and publication surfaces must prioritize readability, provenance, and polish.
They should feel presentable enough to share outside the app.

## Platform overlays

### macOS

macOS surfaces must respect:

* titlebar and toolbar integration
* sidebar expectations
* sheet and dialog conventions
* strong dark-mode legibility
* restrained chrome and clear content hierarchy

### Windows

Windows surfaces must feel natural under Fluent-style expectations:

* clear shell structure
* strong focus and selection treatment
* useful command bars and content grouping
* dense but readable information layout

### Linux

Linux surfaces must stay simple, explicit, and robust:

* avoid chrome-heavy ornament
* prefer clear borders, grouping, and state treatment
* keep dialogs and error posture honest and boring

## Design tokens and spacing rules

The shared spacing ramp is:

* 4
* 8
* 12
* 16
* 24
* 32
* 40
* 48

Tokenized typography must preserve:

* strong page or pane title
* clear section title
* readable dense-data labels
* compact secondary copy
* contrast-safe metadata

Color should be used mostly for:

* selection
* emphasis
* state
* interactive focus

It must not be used as decoration that competes with the data.

## AI generation contract

When AI generates or refactors a user-facing surface, the prompt must include:

* the target surface type
* the target platform or platform family
* the primary user job
* the relevant density posture
* the token family and theme rules
* the required state variants
* the rule that platform conventions must be respected rather than flattened away

The prompt must not merely say "make it prettier."

It must specify:

* layout grammar
* command hierarchy
* state model
* accessibility expectations
* dark-theme expectations
* acceptance screenshots to produce

## AI review loop

No promoted AI-designed surface is accepted on first draft.

The minimum loop is:

1. Generate a layout or component proposal against this contract.
2. Render screenshots for the relevant light and dark themes and for the intended window sizes.
3. Critique the result against a fixed rubric.
4. Revise until the major rubric failures are gone.

### Required critique rubric

The review must explicitly score:

* Is the primary action obvious?
* Is the information hierarchy clear at a glance?
* Does the screen stay legible in light and dark themes?
* Do selection, focus, warning, stale, and error states read clearly?
* Does the layout fit the target platform?
* Does the surface feel authored for its job instead of generic?
* Would a paying user describe the result as deliberate and polished?

## Flagship acceptance consequences

A surface is not flagship grade if:

* it technically works but looks uncomposed
* its dark theme is not trustworthy
* it reuses a layout grammar that does not fit the job
* it depends on hidden hover state, ambiguous labels, or accidental contrast
* each head reinvents selection, warnings, preview state, or recovery posture independently

Flagship proof for every promoted surface must therefore include:

* token and theme evidence
* screenshot or visual-regression evidence
* explicit error/empty/stale/conflict-state evidence
* platform-fit review for the promoted head

## Ownership split

`chummer6-design` owns:

* the cross-surface design contract
* layout grammar canon
* flagship-quality review rubric
* platform-fit expectations

`chummer6-ui-kit` owns:

* shared tokens and theme compilation
* reusable primitives
* shell chrome building blocks
* dense-data and state primitives
* accessibility-safe implementation substrate

`chummer6-ui`, `chummer6-mobile`, and `chummer6-hub` own:

* applying this canon correctly for their heads
* proving the result with real promoted-surface evidence
