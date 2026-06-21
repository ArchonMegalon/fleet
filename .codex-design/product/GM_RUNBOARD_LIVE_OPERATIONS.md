# GM Runboard Live Operations

**Product:** Chummer6 / SR Campaign OS
**Design area:** Chummer Campaign, Chummer Play, Desktop GM Surface
**Status:** Proposal

## Product promise

The GM cockpit is the table-command surface.

Campaign Workspace is for preparation, continuity, notes, packets, and between-session truth.
The GM cockpit is for the current scene, the next ruling, the next consequence, and the next
thirty seconds of play.

If the surface looks like a Horizons inventory, an admin dashboard, or a backlog browser, the
design has failed.

## Core design rule

The cockpit must optimize the next five minutes of live play.

That means:

* one primary situation at a time
* visible pressure, not hidden tabs
* fast adjudication buttons, not rows of product cards
* the current table state always visible
* no dependency on a VTT map
* no second source of campaign truth

## First-screen shape

The first viewport should feel like a command desk, not a catalog.

```text
Top bar
  Session title | active scene | ruleset | elapsed session time | pause/resume

Left rail
  Crew board
  Initiative ladder
  player condition / edge / matrix / astral posture

Center command stage
  Current scene card
  active objective
  opposition posture
  live heat clocks
  consequence queue
  quick adjudication controls

Right rail
  Table Pulse Live
  Black Ledger projection watch
  remote reactions inbox
  open rulings
  GM notes scratchpad

Bottom strip
  one-click scene outcomes
  recap capture
  open aftermath
  ResolutionReport
```

## Surface modes

The cockpit should not be one long scrolling screen. It should have four explicit command modes.

### 1. Run

This is the default live table view.

It shows:

* active scene
* initiative
* player and opposition state
* live heat clocks
* current complications
* one-click rulings and consequence actions

This is the mode the GM stays in during most play.

### 2. Pressure

This is the Table Pulse / Black Ledger consequence view.

It shows:

* security pressure
* matrix pressure
* magic or astral pressure
* law and media pressure
* faction pressure
* packet recipients
* suppression and hold controls
* whether a consequence is table-only, private aftermath, or public-safe Black Ledger candidate

This mode is where the GM decides whether heat becomes a packet, a rumor, a faction move, or
nothing.

### 3. Rulings

This is the fast explain-and-decide mode.

It shows:

* active dispute
* rule text anchors
* ALICE rules coach answer
* house rule posture
* GM override notes
* final ruling button

The output is a ruling receipt, not a chat transcript.

### 4. Aftermath

This is the closeout lane.

It shows:

* unresolved consequences
* injury and expense carry-forward
* faction changes
* Black Ledger candidate outcomes
* recap bundle generation
* next-session hooks

This mode should open directly from the Run mode once a scene or session ends.

## Visual language

The cockpit should read as premium tactical software, not office software.

Required traits:

* dark restrained base
* high-contrast text
* one prominent focus panel
* color only for meaning: danger, pressure, approval, blocked, pending
* dense but quiet layout
* fixed rails and stable components
* no product marketplace cards
* no decorative metrics that do not change a decision

The visual reference is closer to a serious command table than a software admin console.

## Graphics direction

The cockpit should not rely on flat boxes and text density alone. It needs a small number of
high-value graphics that communicate table state immediately.

### 1. Situation backdrop

The center command stage should always sit on top of a scene-grade backdrop:

* rain-slick alley
* sterile lab
* corporate lobby
* warehouse interior
* astral disturbance
* grid-overwatch matrix scene

This is not decorative wallpaper. It is a blurred, darkened, readable scene plate that tells the
GM what kind of pressure they are currently running.

### 2. Heat graphics

Heat should be graphic, not numeric-first.

Use:

* segmented radial clocks
* rising pressure bars
* district or faction signal pips
* color-coded threshold markers
* pulse animation only when a threshold is newly crossed

The GM should understand danger by shape and color before reading text.

### 3. Crew identity strip

Each runner should have:

* portrait chip or silhouette
* faction-color accent
* role icon
* quick state badges

This prevents the left rail from degenerating into anonymous rows.

### 4. Opposition graphics

Opposition should use carded tactical tokens, not spreadsheet rows.

Each opposition token shows:

* unit portrait or silhouette
* role
* armor / threat / alert posture
* current status
* one dominant action cue

Think "small tactical dossier card", not "table row with numbers".

### 5. Pressure map mini-view

The cockpit should include a compact pressure map that can switch between:

* local scene
* district
* matrix layer
* astral layer
* faction layer

This should visually echo Black Ledger without turning into the full public map.

### 6. Consequence cards

Every consequence in the queue should be a visual card with:

* source icon
* urgency edge
* short summary
* likely outcome
* action buttons

Cards should feel like dispatches arriving at a command desk.

## Art direction

The art should feel cinematic but operational.

Required qualities:

* photoreal or high-grade rendered scene plates
* restrained blue/steel/charcoal base with selective amber/red/cyan signals
* subtle scanline, glass, and light-spill treatment only where it improves hierarchy
* no generic gradient blobs
* no toy-like neon overload
* no flat SaaS dashboard cards

Reference blend:

* XCOM situation room discipline
* premium broadcast graphics
* tactical tabletop command software
* Black Ledger’s more serious city-intel mood

## Motion language

Motion should be sparse and meaningful.

Allowed:

* heat pulse when a threshold changes
* card slide-in for new consequences
* soft focus shift when changing modes
* initiative marker movement
* map layer crossfade

Not allowed:

* constant shimmer
* decorative looping motion everywhere
* fake HUD noise
* busy particle effects

## Screenshot bar

This design is not accepted until screenshots prove:

* a first-screen command stage with a readable scene plate
* a left crew rail that does not look like plain rows
* visible heat clocks
* visual consequence cards
* a compact pressure map
* a mode switch between Run / Pressure / Rulings / Aftermath
* a polished dark premium surface with readable text and restrained signal color

## Primary modules

### Crew board

For each player:

* alias / portrait chip
* initiative
* damage
* edge or equivalent economy
* matrix / astral / physical posture
* status flags

Collapsed by default to compact chips. Expand on demand.

### Opposition board

Do not show a giant generic list.

Group opposition by:

* current wave
* threat role
* readiness state
* notable powers
* break / flee / escalate thresholds

The GM should be able to mark damage, routed status, reinforcements, and removals in one click.

### Heat clocks

Heat must be visual and directional.

Each clock needs:

* current level
* why it rose
* next threshold
* likely outcome
* whether the outcome is automatic, review-required, or suppressed

This is where Table Pulse Live stops being abstract.

### Consequence queue

This is the GM’s decision inbox.

Entries look like:

* `Knight Errant attention rising`
* `matrix trace may complete next round`
* `faction rumor available`
* `player contact can intervene`

Each queue item has:

* acknowledge
* defer
* convert to packet
* project to Black Ledger candidate
* dismiss with note

### Rulings desk

The rulings desk must be embedded, not a separate utility window.

For an active ruling it shows:

* question
* ruleset
* exact local context
* ALICE explanation
* related house rule
* final GM call

The GM should be able to resolve a rules disagreement without leaving the cockpit.

## Relationship to Horizons

Horizons is capability discovery.
GM cockpit is live play command.

They should not share the same visual grammar.

Horizons can stay as a separate workbench index, but the GM cockpit entry must open straight into
an active command surface with:

* a session selector
* a “resume live session” button
* a “start cold-open” button
* recent runs
* pending aftermath items

No LTD registry rows, no product tiles, no maintenance copy.

## Relationship to Origin Dossier

The cockpit may steer an origin dossier, but it does not replace it.

Two supported cases exist:

### Before character creation

The GM can launch a bounded origin steer from campaign command:

* campaign tone
* legality posture
* sponsor or fixer seed
* faction pressure
* district or neighborhood
* explicit allowances or exceptions

That steer may seed ALICE and the Origin Dossier flow before the player commits the build.

### After character creation

The GM can attach the same steer to an existing runner and generate additive dossier output:

* story
* portraits
* scene plates
* audiobook
* dossier video

This post-build flow must not silently rewrite the established sheet.

## GM gimmick posture

The GM gimmick is a bounded dramatic steering control, not a joke side tool.

It may influence:

* opening premise
* pressure flavor
* likely antagonists
* social and faction hooks
* scene-prompt selection
* dossier-bundle media direction

It may not:

* grant itself rule authority
* bypass player consent
* auto-apply rewards or penalties
* override sheet truth without an explicit edit

## ALICE in the cockpit

Inside the cockpit, ALICE needs one extra bounded affordance beyond Explain, Suggest, and Recap:

* `Seed origin` turns current campaign posture and GM steer into dossier context for one runner

The result is not live world truth. It is a dossier-context packet that can later become:

* a player-facing origin story
* a portrait selection set
* a scene bundle
* an audiobook request
* a dossier video request

## ALICE in the cockpit

ALICE should have three bounded GM roles inside the cockpit:

* `Explain`: rules and tradeoff explanation
* `Suggest`: pressure-safe next-step suggestions
* `Recap`: aftermath and carry-forward synthesis

ALICE should never take over the main screen. She should live in a side rail or drawer and write
receipts back into the active scene.

## Black Ledger relationship

Black Ledger is not the cockpit. It is the projection and consequence surface downstream of it.

The cockpit decides:

* what happened
* what pressure changed
* what becomes a packet
* what becomes a private aftermath note
* what is eligible for Black Ledger projection

The cockpit therefore needs an explicit `public-safe projection candidate` state and an explicit
`private only` state.

## Acceptance bar

The design passes only if:

* a GM can run a scene without opening the broader workspace
* the first screen shows command, not navigation
* heat and consequences are visible at a glance
* a ruling can be resolved in one place
* Table Pulse Live and Aftermath remain separate
* Black Ledger projection is downstream, not fused into raw live play
* the surface feels like a command tool, not an internal maintenance tool

## Data dependencies

The cockpit consumes:

* `ActionBudgetResult`
* condition and effect receipts
* `CrewCapabilityVector`
* `MissionFitCheck`
* `JobPacket`
* `ResolutionReport`
* Table Pulse Live receipts
* Black Ledger projection candidates
* ALICE rules and recap packets

## Repo split

* `chummer6-ui`: desktop GM cockpit
* `chummer6-mobile`: player table cards and GM-lite assistive view
* `chummer6-core`: action, effect, heat, and explain truth
* `chummer6-hub`: session continuity and closeout
