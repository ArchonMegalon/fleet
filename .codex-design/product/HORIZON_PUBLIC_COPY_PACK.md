# Human-Facing Horizon Copy Pack

**Product:** Chummer 6 / SR Campaign OS
**Primary repo:** `chummer6-design`
**Status:** Draft copy / public-guide-ready prose
**Scope:** Human-facing descriptions for all current horizons except BLACK LEDGER and KARMA FORGE, which already have separate long-form public descriptions.
**Use:** Public guide, `chummer.run`, horizon pages, roadmap pages, ProductLift feature explanations, Katteb content briefs, vidBoard scripts, and launch copy.

## How to use this file

This file is intentionally written in public-facing product language. It sells the fantasy hard while preserving the Chummer trust model:

- horizons are future-capability lanes, not shipment promises;
- AI and LTD tools may assist, but Chummer-owned truth remains authoritative;
- mechanics truth stays deterministic and receipt-backed;
- session-analysis lanes remain opt-in, private, and non-authoritative;
- external tools are projection, routing, discovery, rendering, or research helpers, not systems of record.

Recommended repo use:

```text
products/chummer/HORIZON_PUBLIC_COPY_PACK.md
```

Or split into:

```text
products/chummer/horizons/public-copy/quicksilver.md
products/chummer/horizons/public-copy/edition-studio.md
...
```

BLACK LEDGER and KARMA FORGE are intentionally not repeated here except through cross-links.

# QUICKSILVER — build at the speed of thought

**QUICKSILVER is Chummer’s expert-speed horizon: the future where power users stop waiting on the interface and start moving through dense builds, comparisons, inspections, and edits as fast as they can think.**

Chummer can be correct and still feel slow.

A builder who knows what they want should not fight click friction.
A GM tuning opposition should not dig through modal after modal.
A creator reviewing a package should not lose context every time they inspect a value.
A veteran user should not need five screens to answer one mechanical question.

QUICKSILVER is the answer to that.

It is not a new rules engine.
It is not a shortcut skin.
It is not “keyboard-only mode for elites.”

It is the horizon where Chummer becomes **fast without becoming careless**.

## The promise

**Everything important stays explainable, but nothing obvious gets in your way.**

QUICKSILVER lets experienced users:

- search instantly
- jump instantly
- compare instantly
- batch-edit safely
- pin inspectors
- keep context while moving
- undo dangerous work
- cancel long operations
- inspect receipts without losing flow
- move through complex builds without waiting on the UI

The product should feel like:

> “I know what I want. Chummer keeps up.”

## What it feels like

A user is building a decker.

They type:

```text
/cyber deck hot-sim rating>=4 price<...
```

Chummer narrows the catalog before the user finishes typing.

They press a shortcut and pin a comparison drawer.

They batch-select three gear options, preview legality impact, and apply the safest change.

The companion says:

> “That works. You saved nuyen, lost one edge-case bonus, and did not accidentally break the campaign’s availability overlay. Rare restraint.”

The user never leaves the workbench.
The receipts remain visible.
The state stays safe.

That is QUICKSILVER.

## What it should include

### Command surface

A command palette for common actions:

- jump to attribute
- add gear
- compare weapons
- inspect legality
- explain value
- open receipt
- find conflict
- pin build section
- export packet
- switch rule environment
- show changed items
- run preflight

Command examples:

```text
> compare current build to last legal snapshot
> show illegal items
> add availability-safe deck
> explain initiative
> export GM-safe summary
> find gear with wireless bonus
```

### Shortcut-first flows

Experienced users should be able to operate Chummer like an instrument:

- build navigation
- inspector toggles
- compare panes
- bulk changes
- undo/redo
- open receipts
- switch variants
- jump to conflict
- apply safe fix

### Dense-state inspectors

The workbench should support:

- pinned side-by-side inspectors
- split views
- always-visible legality state
- “why changed?” drawers
- active rule-environment badges
- compact receipt trails
- conflict queues

### Batch-safe editing

Speed only works if the user can trust it.

Batch edits need:

- preview before apply
- transactional apply
- cancel-safe operations
- undo
- legality preflight
- receipt generation
- partial failure explanation

### Fast search and compare

Search should be:

- instant
- fuzzy
- filterable
- keyboard-friendly
- ruleset-aware
- package-aware
- environment-aware

Compare should show:

- cost deltas
- legality deltas
- availability deltas
- role impact
- tradeoffs
- receipts
- “what got worse?” not just “what changed?”

## What users want to know

### Is this for beginners?

Not primarily. QUICKSILVER helps expert users move faster. Beginners should still get ONRAMP and guided mastery.

### Will it hide explanations?

No. QUICKSILVER must keep receipts and explanations available. Fast does not mean blind.

### Will keyboard users get special power?

Keyboard users get speed. Mouse/touch users still get the normal guided path.

### Can it break my build faster?

No. Batch editing must be previewed, reversible, and receipt-backed.

### Does this replace Build Lab?

No. QUICKSILVER is the speed surface. Build Lab / ALICE is the analysis surface. They should reinforce each other.

## What it is not

QUICKSILVER is not:

- unsafe caching
- stale UI state
- keyboard-only elitism
- hidden legality
- command-line theater
- a second rules engine
- a way to mutate builds without receipts

Speed only matters if the user still trusts the result.

## The first slice

The first useful QUICKSILVER slice should be:

**Command Palette + Pinned Inspector + Conflict Queue**

It should let a user:

1. open command palette
2. jump to any build section
3. run legality preflight
4. pin “why illegal?” inspector
5. apply one safe fix
6. see receipt
7. undo

Success looks like:

> A veteran user fixes a broken build in thirty seconds without leaving the workbench or losing the explanation.

## The vision

Chummer should eventually feel like a professional tool.

Not because it is obscure.
Because it respects expertise.

**QUICKSILVER is the moment Chummer stops merely being powerful and starts feeling fast enough to deserve that power.**

# EDITION STUDIO — every edition deserves its own voice

**EDITION STUDIO is Chummer’s authored-edition horizon: the future where SR4, SR5, and SR6 do not feel like one generic shell with different data, but like deliberately crafted experiences that preserve each edition’s meaning.**

A single generic interface can technically support multiple editions.

But Shadowrun editions do not think the same way.

They differ in terminology.
They differ in priorities.
They differ in character flow.
They differ in what users need explained.
They differ in which mistakes are common.
They differ in how the table talks about the game.

If Chummer flattens all of that into one neutral shell, it loses clarity exactly where users need help most.

EDITION STUDIO fixes that.

## The promise

**Shared product. Authored editions. No fork chaos.**

Chummer should support multiple rulesets without turning into three disconnected apps.

Each promoted edition should get:

- edition-aware terminology
- edition-aware prompts
- edition-aware inspectors
- edition-aware build guidance
- edition-aware explanation flow
- edition-aware density and emphasis
- edition-aware theme/motion where useful
- edition-aware examples
- edition-aware “what changed from another edition?” help

But all of it still sits on shared Chummer truth:

- deterministic engine
- rule environments
- receipts
- portability
- shared workspace
- shared publication/export pipeline
- shared account/install/support model

The edition gets a voice.
The product keeps one spine.

## What it feels like

A user opens SR6.

The UI talks like SR6.
The build flow emphasizes SR6-specific pain.
The explain view expects SR6-specific confusion.
The companion’s advice knows what users usually misunderstand in SR6.

A user opens SR5.

The UI does not pretend SR5 is just SR6 with different labels.
The comparison, legality, and build-flow prompts respect SR5 semantics.

A user opens SR4.

Chummer does not fake parity by hiding difference.

The user feels:

> “This edition was understood, not merely loaded.”

## What it should include

### Edition-specific product heads

Each major ruleset can have an authored surface:

- SR4 head
- SR5 head
- SR6 head

These heads share primitives but diverge where meaning diverges.

### Edition-aware prompts

Examples:

- “This is usually where SR6 players misread Edge economy.”
- “This SR5 choice affects availability differently than your SR6 muscle memory expects.”
- “This SR4 import needs review because the semantic mapping is lossy.”

### Edition-specific inspector posture

Inspectors should emphasize what matters for that edition:

- common illegal choices
- edition-specific dependencies
- known migration traps
- old-Chummer expectations
- terminology users actually search for

### Migration help

A user coming from Chummer5a should get:

- what still exists
- what changed
- what is not yet supported
- what can import
- what imports lossy

### Theming with purpose

Visual differences should help comprehension.

Do not theme just for nostalgia.

Use:

- density
- color posture
- motion
- grouping
- icon emphasis
- inspector layout

only where it makes the edition easier to understand.

## What users want to know

### Does this mean three separate apps?

No. Chummer remains one product. EDITION STUDIO gives each promoted ruleset an authored head on the shared spine.

### Will edition flavor change mechanics?

No. Mechanics stay in the engine. Styling and copy never become rules truth.

### Can I compare or migrate between editions?

Eventually, yes, where mappings are safe. But Chummer must show when a mapping is lossy or impossible.

### Is this only cosmetic?

No. Cosmetic-only theming is explicitly not enough. EDITION STUDIO is about semantic clarity.

## What it is not

EDITION STUDIO is not:

- decorative skins
- nostalgia themes
- three disconnected apps
- rules truth from UI flavor
- one generic screen with renamed labels
- edition wars disguised as design

It is authored product expression.

## The first slice

The first useful slice should be:

**SR6 authored workbench posture + Chummer5a migration helper**

It should:

1. define SR6 terminology and inspector posture
2. highlight SR6-specific build traps
3. provide “coming from Chummer5a?” help
4. show where imports are clean, lossy, or blocked
5. preserve shared Chummer navigation and receipts

Success looks like:

> A Chummer5a veteran can open Chummer6 and understand what changed without feeling abandoned or patronized.

## The vision

Chummer should not treat editions like interchangeable datasets.

Each edition deserves a product voice.

**EDITION STUDIO is where Chummer becomes one trusted platform with multiple authored Shadowrun heads — clear where they are shared, honest where they diverge.**

# ONRAMP — from confused to competent

**ONRAMP is Chummer’s guided-mastery horizon: the future where new, rusty, or overwhelmed users can build confidence before they drown in options, jargon, and legality warnings.**

Shadowrun is not simple.

A new player can hit a wall before they ever feel the fun.
A returning player may remember the vibe but not the rules.
A GM may want a new player at the table but not want to review a broken sheet for an hour.
A mobile-only player may want to join an open run but not have the full desktop setup yet.

Chummer should not only serve experts.

It should teach users how to become experts.

That is ONRAMP.

## The promise

**Chummer should help you make your first good decision, then your next one, then your next one.**

ONRAMP does not auto-build a character and hide the rules.

It guides.

It says:

- here is a safe start
- here is what this choice means
- here is why this conflict happened
- here is how to recover
- here is what to fix before applying to a run
- here is what you can ignore for now
- here is what matters later

ONRAMP turns complexity into a path.

## What it feels like

A new player says:

> “I want to play a decker, but I do not know where to start.”

Chummer answers:

> “Great. You need to care about Matrix ability, gear budget, survivability, and what your table’s rule environment allows. Let’s start with a safe decker shell.”

The player sees three starters:

- street-level decker
- social infiltrator/decker
- combat-support decker

They pick one.

Chummer explains the first three meaningful choices, not every option in the game.

When the build becomes illegal, Chummer says:

> “This is blocked by your table’s availability overlay. You can replace it, ask the GM, or switch to a campaign-approved quickstart.”

The user learns because Chummer shows the why.

## What it should include

### Guided starter lanes

Starter lanes for:

- decker
- face
- street samurai
- mage
- rigger
- technomancer
- support/infiltration
- beginner-friendly hybrid

Each lane should include:

- what this role does
- what choices matter early
- common traps
- example builds
- safe variants
- campaign-rule warnings

### Progressive disclosure

Do not hide complexity forever.

Reveal it in layers:

1. role fantasy
2. core decisions
3. legality
4. gear
5. optimization
6. campaign-specific constraints
7. advanced tradeoffs

### Recovery help

When something breaks, Chummer should offer:

- explain conflict
- safe replacement
- compare alternatives
- ask GM
- switch preset
- open receipt
- ignore until later if safe

### Open-run readiness

For Shadowcasters/open runs, ONRAMP should help users answer:

- Can I apply with this runner?
- Does this table allow quickstarts?
- What rule environment applies?
- What is my best role?
- What should I fix first?
- Can I join from mobile?

### Guided GM start

ONRAMP should also help beginner GMs:

- pick a beginner job
- select quickstart runners
- set join policy
- write safety notes
- schedule a session
- use a prep checklist
- file a resolution report

## What users want to know

### Will Chummer build the character for me?

It can offer safe starters and suggestions, but it should show why choices matter. It is not a black box.

### Can I still customize?

Yes. ONRAMP teaches the path; it does not lock you into a template.

### Does it work with house rules?

It should. ONRAMP must read the active rule environment and explain table-specific conflicts.

### Can I use it on mobile?

Eventually, yes. Mobile-first quickstart and open-run participation are core reasons this horizon matters.

### Does this replace expert mode?

No. ONRAMP and QUICKSILVER are complements: one teaches, one accelerates.

## What it is not

ONRAMP is not:

- hidden auto-build
- shallow tutorial theater
- wrong-but-friendly advice
- a replacement for receipts
- a way to hide legal conflicts
- one happy path that fails on real builds

It must survive real user mistakes.

## The first slice

The first ONRAMP slice should be:

**Beginner-friendly open-run application with quickstart runner**

It should let a new player:

1. find a beginner open run
2. choose quickstart runner
3. see active rule environment
4. pass preflight
5. acknowledge table contract
6. apply
7. get accepted
8. receive a player-safe briefing

Success looks like:

> A new player without a full desktop setup joins their first Chummer-mediated run without breaking the GM’s workflow.

## The vision

Chummer should not make users prove they deserve the product.

It should earn their confidence.

**ONRAMP is where Chummer becomes the guide that turns Shadowrun from intimidating to playable without ever lying about the rules.**

# RUN CONTROL — the GM’s command center

**RUN CONTROL is Chummer’s GM operations horizon: the future where campaign prep, rosters, scenes, agendas, live state, recaps, and handoffs live in one trustworthy workspace instead of scattered notebooks, chats, calendars, and memory.**

A good character tool is not enough.

GMs need to know:

- who is playing
- what runners are ready
- what rule environment applies
- what the next run is
- what scenes matter
- what opposition is prepared
- what happened last time
- what changed after the run
- what needs to become a recap, dossier, or world consequence

If Chummer wants to become a campaign OS, it must help the GM operate the table.

That is RUN CONTROL.

## The promise

**The GM should be able to open one place and know what is safe to run next.**

RUN CONTROL gives the GM:

- roster state
- runner readiness
- rule-environment status
- session agenda
- scene list
- NPC/opposition packets
- handouts
- run objectives
- open questions
- recap status
- player-safe/share-safe boundary
- BLACK LEDGER links
- post-session resolution prompts
- publication handoff

The GM does not need to:

- leave the table to update every sheet
- reconstruct the campaign by memory

The workspace carries the burden.

## What it feels like

The GM opens the campaign workspace.

Chummer says:

```text
Tonight's run:
Extraction at the Black Clinic

Roster:
4 accepted, 1 waitlisted

Warnings:
- one runner has stale rule environment
- Matrix role filled
- no dedicated face
- two players have not acknowledged content notes

Prep ready:
- player-safe briefing
- opposition packet
- runsite preview
- run objectives
- reward hooks
- failure consequences

Next safe action:
review stale runner or start session with manual override
```

The GM does not need to reconstruct the campaign by memory.

The workspace carries the burden.

## What it should include

### Campaign dashboard

- active roster
- upcoming run
- open runs
- unresolved threads
- recent changes
- rule-environment health
- runner readiness
- pending intel
- world tick consequences
- recent artifacts
- support/status notes if relevant

### Run board

For each run:

- objective
- scenes
- expected tone
- content notes
- player-safe pitch
- GM-only notes
- opposition packets
- runsite assets
- reward/failure consequences
- scheduling state
- meeting handoff
- Table Pulse/GOD consent
- resolution status

### Scene control

Scenes should support:

- title
- objective
- NPCs
- opposition
- location
- clues
- handouts
- heat risks
- optional events
- recap notes
- “mark for follow-up”

### Roster control

The GM should see:

- accepted players
- runner dossiers
- role coverage
- build legality
- rule-environment conflicts
- schedule status
- consent acknowledgements
- readiness flags
- no-show/waitlist state

### Post-session closeout

After play:

- file resolution
- update contacts
- update heat
- issue rewards
- flag unresolved scenes
- create recap
- update BLACK LEDGER
- generate news candidates
- produce player-safe artifacts

## What users want to know

### Does this replace Discord, Teams, Foundry, or Roll20?

No. RUN CONTROL owns Chummer preparation. External tools remain meeting/play surfaces.

### Can it work for home games?

Yes. RUN CONTROL should work for private campaigns before broad public network play.

### Can it work with BLACK LEDGER?

Yes. BLACK LEDGER produces world pressure and job packets. RUN CONTROL turns adopted work into table-ready prep and closeout.

### Can it generate recaps?

Yes, but recaps must be source-linked and GM-approved before publication.

## What it is not

RUN CONTROL is not:

- a VTT replacement
- a generic team project board
- an AI GM
- hidden campaign state
- live surveillance
- calendar-owned truth
- a recap generator that invents what happened

It is a GM operating surface built on Chummer-owned campaign truth.

## The first slice

The first RUN CONTROL slice should be:

**Starter run dashboard**

It should let a GM:

1. adopt or create a run
2. set roster
3. set table contract
4. attach rule environment
5. schedule through a receipt path
6. prep opposition packet
7. run readiness check
8. file resolution
9. generate player-safe recap

Success looks like:

> A GM can run a beginner one-shot without stitching together Chummer, Discord pins, spreadsheets, and memory.

## The vision

The GM should not need five tools to remember what is happening.

**RUN CONTROL is where Chummer becomes the command center for prep, play, closeout, and campaign memory.**

# NEXUS-PAN — your table stays in sync

**NEXUS-PAN is Chummer’s session-continuity horizon: the future where phones, tablets, laptops, desktops, and web surfaces stay aligned during play even when devices drop, reconnect, or change roles.**

At a table, trust breaks quickly.

A player reconnects and sees old state.
The GM changes something and one device misses it.
A tablet goes offline.
A phone comes back with stale data.
A desktop has the real value, but nobody knows why.
The table stops believing the screens.

NEXUS-PAN is the promise that Chummer can recover honestly.

## The promise

**Device churn should not break table confidence.**

NEXUS-PAN keeps shared state:

- visible
- explainable
- replayable
- conflict-aware
- reconnect-safe
- role-aware
- local-first where needed
- honest when degraded

It does not pretend every device is always current.

It tells the truth:

```text
You are offline.
You have 3 pending changes.
The table has advanced 2 events.
This field is stale.
Reconnect can merge safely.
This conflict needs review.
```

That honesty is the feature.

## What it feels like

A player loses connection mid-session.

They come back ten minutes later.

Chummer says:

```text
Reconnected.

You missed:
- initiative round advanced
- condition monitor changed
- GM added one private note

Your local note can merge safely.
Your old gear edit conflicts with the current campaign state.

Next safe action:
review conflict or discard local edit.
```

The GM does not rebuild context by memory.

The player returns to the table.

## What it should include

### Device roles

Different devices do different jobs:

- desktop workstation
- GM laptop
- player phone
- play tablet
- observer screen
- travel/offline device
- preview scout device

NEXUS-PAN should know what each device is for.

### Reconnect receipt

Every reconnect should be explainable:

- what changed while offline
- what merged
- what stayed local
- what conflicted
- what is stale
- what needs review

### Shared session state

The table state should include:

- campaign context
- roster
- active run
- runner readiness
- open scenes
- marked moments
- handouts
- visible clocks
- device-specific state
- pending closeout

### Conflict recovery

No silent last-write-wins for important state.

When truth diverges:

- show conflict
- show sources
- offer safe actions
- preserve local copy
- produce receipt

### Offline mode

A device should be able to:

- keep useful local state
- show stale/pending status
- collect notes
- mark moments
- sync later

Without pretending offline state is table truth.

## What users want to know

### Can I play if my connection drops?

NEXUS-PAN aims to make reconnect boring and recoverable.

### Will it silently overwrite my changes?

No. Important conflicts need visible recovery, not silent last-write-wins.

### Can different devices have different roles?

Yes. Device-role awareness is central.

### Does this replace cloud sync?

No. It builds on Chummer-owned account, install, campaign, and roaming workspace truth.

### Can it work offline?

It should support useful local continuity while clearly showing what is stale or pending.

## What it is not

NEXUS-PAN is not:

- magical sync
- hidden merge behavior
- a second session history
- truth by whichever device posted last
- always-online dependence

It is the boring reliability layer that makes live features safe.

## The first slice

The first slice should be:

**Reconnect receipt for mobile session state**

It should show:

1. offline state
2. missed events
3. pending local changes
4. safe merges
5. conflicts
6. next safe action

Success looks like:

> A player reconnects mid-session and nobody at the table loses trust.

## The vision

Shadowrun tables already have enough chaos.

The devices should not add more.

**NEXUS-PAN is where Chummer becomes the network of the table — honest when disconnected, boring when restored, and trusted when play gets messy.**

# ALICE — build smarter before the run explodes

**ALICE is Chummer’s build-simulation and what-if horizon: the future where players can compare builds, catch trouble, test upgrade paths, and understand tradeoffs before the table discovers the mistake under pressure.**

Many weak builds are not obvious at creation time.

A player thinks they built a decker.
The table discovers they cannot afford the gear that makes the role work.
A face has social dice but no survival path.
A combat build hits hard once and then collapses.
A table discovers their favorite option is now campaign-illegal.

ALICE exists so Chummer can say:

> “This is legal, but it may not do what you think.”

## The promise

**Grounded build advice without invented mechanics.**

ALICE should compare, simulate, and explain using Chummer-owned engine truth.

It can help answer:

- Which build is stronger for this role?
- Which option gives the better tradeoff?
- What breaks if I switch campaigns?
- Which upgrade path makes sense?
- What is a role trap?
- What does campaign change?
- What is legal but fragile?
- What can I fix quickly?

But ALICE must never invent rules.

Every claim needs a receipt.

## What it feels like

A player compares two builds:

```text
Variant A: decker/infiltrator
Variant B: pure decker
```

ALICE says:

```text
Variant B is stronger for Matrix-first runs.
Variant A is safer for mixed social infiltration.

Tradeoffs:
- Variant B improves core Matrix capability.
- Variant A survives better outside the host.
- Variant B exceeds your campaign’s starting gear budget unless the GM approves a black-channel exception.
- Variant A leaves you weaker against heavy IC.

Recommended next question:
Are you joining a Matrix-heavy campaign or a mixed-op open run?
```

Buttons:

- Show math
- Show receipts
- Compare team role fit
- Fix budget issue
- Keep my chaos

That is ALICE.

## What it should include

### Build comparison

Compare:

- current build vs snapshot
- variant A vs variant B
- runner vs campaign rule environment
- runner vs team needs
- current build vs upgrade goal
- quickstart vs custom build

### Tradeoff briefs

Not just “better/worse.”

Show:

- what improves
- what worsens
- what becomes illegal
- what becomes expensive
- what becomes fragile
- what depends on campaign context
- what role the build actually fits

### Trap detection

Detect:

- archetype drift
- underfunded role
- missing required gear
- weak survivability
- illegal package conflict
- bad upgrade path
- duplicate team role
- campaign mismatch
- hidden dependency

### Upgrade path planning

Help users ask:

- what should I buy next?
- what is the cheapest meaningful upgrade?
- what becomes available after this run?
- what should I not buy yet?
- what does this faction/world offer unlock?

### Team analysis

For campaigns and open runs:

- role coverage
- unresolved role
- missing Matrix/magic/social/combat coverage
- build conflicts
- quickstart recommendations

## What users want to know

### Is ALICE AI?

It may use assistant phrasing or drafting support, but mechanics come from Chummer-owned engine truth.

### Will ALICE tell me the “best” build?

It should explain tradeoffs, not erase player taste.

### Can it work with house rules?

Yes. It must understand the active rule environment and show what changed.

### Can it help with open runs?

Yes. It can show whether a runner fits a GM’s open-run joining policy.

### Can it be funny?

Yes. The companion can comment. The receipts still do the serious work.

## What it is not

ALICE is not:

- a hidden optimizer
- a build police bot
- an AI rules engine
- a powergaming-only tool
- legality by vibes
- advice without receipts

It should help users think, not replace them.

## The first slice

The first ALICE slice should be:

**Build comparison brief**

It should let a user:

1. select two snapshots or variants
2. compare legality
3. compare role fit
4. compare major costs/tradeoffs
5. see receipts
6. export a short explain brief

Success looks like:

> A player understands why one legal build is worse for their intended run before the session starts.

## The vision

Chummer should not only answer:

> “Is this legal?”

It should also answer:

> “Will this actually work for what I am trying to do?”

**ALICE is where Chummer becomes a build mentor with receipts.**

# KNOWLEDGE FABRIC — rules answers with receipts

**KNOWLEDGE FABRIC is Chummer’s grounded rules-knowledge horizon: the future where players, GMs, operators, and helpers can ask rules questions and get cited, derived, non-hallucinated answers instead of assistant guesses.**

Rules questions are expensive.

The same questions get asked again and again.
Search is fragmented.
Assistants hallucinate.
Players mix editions.
GMs need quick answers.
Support needs consistent explanations.
Build Lab needs grounded help.
KARMA FORGE needs safe context.
Public guide content needs citations and boundaries.

KNOWLEDGE FABRIC is the layer that makes Chummer’s knowledge reusable.

## The promise

**Ask a rules question. Get an answer that shows its source trail.**

The answer should be built from:

- core-owned source packs
- engine receipts
- explain packets
- derived projections
- citations
- search indexes
- graph relationships
- approved public help
- rule-environment context

Not from raw assistant memory.

Not from “the model probably knows Shadowrun.”

## What it feels like

A GM asks:

> “Why is this gear blocked in this campaign?”

Chummer answers:

```text
This item is legal under base SR6 but blocked by Seattle Availability Overlay v1.2.

Source:
- base rules allow the item under normal conditions
- campaign overlay restricts this category
- activation receipt shows the overlay was approved by the GM
- runner dossier currently has one blocked item

Next safe actions:
- replace item
- request GM approval
- open campaign diff
```

The answer has citations, receipts, and a path forward.

## What it should include

### Derived knowledge projections

Build projections from Chummer-owned data:

- rules chunks
- catalog relationships
- engine facts
- explain receipts
- package metadata
- rule-environment diffs
- FAQ/help entries
- search indexes
- graph edges

### Cited answers

Every answer should show:

- source type
- relevant package
- receipt
- rule environment
- whether it is official, campaign, creator, or world-linked
- whether the answer is player-safe or GM-only

### Searchable receipts

Users should be able to find:

- why a value changed
- why an item is illegal
- why a rule environment blocks something
- which package added a modifier
- what changed since last session
- which campaign started the change

### Assistant boundary

Assistants may:

- rephrase
- summarize
- ask clarifying questions
- guide the user to receipts
- draft help copy

Assistants may not:

- compute mechanics
- invent rules
- overrule engine truth
- answer from unverified raw memory

## What users want to know

### Is this a rules chatbot?

No. It is a knowledge projection layer grounded in Chummer truth. Chat may be one interface, not the authority.

### Can it answer official rules questions?

It can answer from available approved source packs and citations, but it must show the source trail and never pretend to know unsupported content.

### Can it answer house-rule questions?

Yes, if the active rule environment provides the relevant package and receipt.

### Can it help support?

Yes. Support can use the same derived knowledge so answers stay consistent.

### Can it help public docs?

Yes. Documentation and guide content can be generated from approved knowledge projections.

## What it is not

KNOWLEDGE FABRIC is not:

- assistant folklore
- raw rulebook dumping
- a second rules engine
- uncited help text
- public support answers without review
- rules truth from embeddings
- a license to bypass receipts

It is derived knowledge with visible source trails.

## The first slice

The first slice should be:

**Cited “why is this illegal?” answer**

It should:

1. detect a legality conflict
2. show active rule environment
3. cite source/pack/receipt
4. explain the conflict in plain language
5. offer safe actions
6. avoid assistant-invented rules

Success looks like:

> A user understands a conflict without asking Discord, support, or the GM to reconstruct the rule chain.

## The vision

Rules-heavy games do not need more confident guessing.

They need grounded answers.

**KNOWLEDGE FABRIC is where Chummer turns receipts, source packs, and explanations into a reusable rules brain that never forgets where the answer came from.**

# JACKPOINT — dossiers, briefings, and recaps with a source trail

**JACKPOINT is Chummer’s short-to-medium-form artifact studio: the future where campaigns produce polished dossiers, mission briefings, recaps, evidence rooms, and narrated packets without losing provenance.**

Tables create material constantly.

Runner dossiers.
Mission briefs.
After-action recaps.
Player-safe summaries.
GM-only evidence.
News cards.
Public proof.
Creator handouts.
Campaign introductions.

Most tools make these outputs prettier by disconnecting them from the truth.

JACKPOINT should do the opposite.

It makes artifacts feel good **because** they are grounded.

The signed-in command lane is already live at `https://chummer.run/jackpoint`.
That lane currently carries first-party briefing packets on real markdown and JSON routes without pretending the whole long-form publishing roadmap is done.

## The promise

**Turn campaign truth into polished artifacts without making things up.**

JACKPOINT can produce:

- dossier packets
- player-safe recaps
- GM-only debriefs
- narrated mission briefings
- evidence rooms
- share cards
- release explainers
- campaign primers
- city ticker cards
- creator preview packets
- support/fix explainers

Every artifact should know:

- what source it came from
- what audience it is safe for
- what changed
- who approved it
- what was rendered
- what was narrated
- what should not be shown

## What it feels like

After a run, the GM clicks:

> Generate recap packet

JACKPOINT asks:

```text
Audience:
- players
- GM-only
- public-safe
- faction-private
```

The GM picks player-safe.

JACKPOINT generates:

- written recap
- key moments
- unresolved threads
- reward summary
- player-safe map marker
- PeekShot share card
- optional narrated audio
- optional vidBoard briefing for next session

The GM sees the source trail.

Nothing private leaks.

The table gets a recap that feels real.

## What it should include

### Dossier packets

For runners, factions, NPCs, runs, or campaigns:

- summary
- current state
- known history
- relationships
- artifacts
- heat/notoriety
- rule-environment context
- source references

### Mission briefings

For GMs and players:

- sponsor
- target
- location
- known risks
- role needs
- expected tone
- public/GM-only split
- reward/failure stakes
- optional presenter video

### Recap artifacts

After sessions:

- what happened
- what changed
- unresolved threads
- rewards
- consequences
- world-tick links
- player-safe version
- GM-only version

### Evidence rooms

For complex events:

- timeline
- source packets
- images/cards
- markers
- receipts
- replay links
- related intel

### Share cards

For public or network-safe moments:

- runner legend
- open run promotion
- faction update
- city ticker
- player-safe map marker
- creator pack preview
- release highlight

## What users want to know

### Will it invent story details?

No. It should work from approved source packets and show what it used.

### Can I control spoilers?

Yes. Audience classification is core: player-safe, GM-only, public-safe, faction-secret, organizer-only.

### Can it make videos?

Yes, where appropriate. vidBoard can support structured presenter briefings; other media lanes can handle narration, cards, and packets.

### Can creators use it?

Yes. JACKPOINT is a natural creator preview and artifact-production lane.

### Is this the same as RUNBOOK PRESS?

No. JACKPOINT is short-form; RUNBOOK PRESS is long-form.

## What it is not

JACKPOINT is not:

- a generic content generator
- lore invention without source
- a replacement for GM approval
- a long-form book pipeline
- a spoiler leak machine
- a media tool owning campaign truth

It is an artifact studio with receipts.

## The first slice

**Mission briefing packet**

A GM starts with one clean packet for the table: the player-facing brief is polished, spoiler-safe, and ready to share before the run begins.

Behind it, Chummer keeps the GM notes, source references, share card, optional presenter brief, and approval state together so the packet stays useful without leaking private material.

The result is simple:

> A GM can hand players a polished briefing and still show exactly where every claim came from.

## The vision

Campaigns should produce artifacts worth keeping.

**JACKPOINT is where Chummer turns the campaign’s truth into things the table actually wants to read, watch, share, and remember.**

# RUNSITE — make the space legible

**RUNSITE is Chummer’s spatial-prep horizon: the future where mission locations become explorable, understandable, and briefing-ready before the action starts.**

GMs describe spaces.
Players misread them.
A club, museum, warehouse, arcology floor, or black clinic can matter enormously, but the table often has no shared mental picture until confusion hits.

RUNSITE fixes that.

It helps the table understand the space before it starts.

The signed-in command lane is already live at `https://chummer.run/runsites`.
That lane currently carries first-party runsite packs on real markdown and JSON routes without pretending the whole spatial roadmap is done.

## The promise

**Mission spaces should be readable before they become dangerous.**

RUNSITE can provide:

- explorable location packs
- floor-plan previews
- route overlays
- hotspots
- entry points
- security zones
- public/GM-only views
- optional narration
- presenter walkthroughs
- embedded context
- share-safe previews
- runsite cards

It is not live combat.
It is not a VTT replacement.
It is spatial briefing and planning.

## What it feels like

A GM prepares a run at a black clinic.

RUNSITE generates a pack:

```text
Player-safe view:
- front entrance
- public waiting area
- staff wing rumors
- loading dock
- known security cameras

GM-only view:
- hidden elevator
- astral ward zone
- drone nest
- emergency extraction tunnel
- prototype storage
```

Players can explore the briefing version.

The GM can keep secrets hidden.

The session starts with everyone understanding the space.

## What it should include

### Explorable packs

Location packets for:

- safehouses
- clinics
- clubs
- hotels
- arcologies
- warehouses
- labs
- museums
- docks
- corporate offices
- magical sites

### Route overlays

Show:

- likely approaches
- escape routes
- choke points
- public routes
- high-risk routes
- faction-controlled zones
- heat zones

### Hotspots

Clickable points:

- camera
- guard post
- locked door
- hidden egress
- public clue
- secret
- objective
- extraction route

### Permissioned views

Every runsite should support:

- player-safe
- GM-only
- faction-secret
- public teaser
- post-run reveal

### Media integration

Use:

- Crezlo Tours for explorable tours
- AvoMap for route and location context
- PeekShot for preview cards
- vidBoard for orientation host clips
- Soundmadeseen for optional narration

## What users want to know

### Is this a tactical map?

No. It is prep and spatial understanding. Tactical play can still happen in a VTT.

### Can the GM hide secrets?

Yes. Visibility tiers are mandatory.

### Can players explore before the session?

Yes, if the GM publishes a player-safe version.

### Can it connect to BLACK LEDGER?

Yes. A world map marker can point to a runsite packet.

### Can creators publish runsites?

Eventually, yes. RUNSITE packs are a natural creator artifact.

## What it is not

RUNSITE is not:

- a VTT replacement
- live combat truth
- token movement
- hidden world truth
- public leakage of GM-only space

It is a permissioned spatial artifact.

## The first slice

The first slice should be:

**Safehouse runsite packet**

It should include:

1. player-safe overview
2. GM-only overlay
3. hotspots
4. route preview
5. share card
6. source/approval receipt

Success looks like:

> A GM sends players a briefing pack, and the table starts the run with a shared mental map instead of ten minutes of confusion.

## The vision

The shadows have places.

Those places should matter.

**RUNSITE is where Chummer makes the spaces of a run legible, explorable, and memorable without taking over the table.**

# RUNBOOK PRESS — campaign books without duct tape

**RUNBOOK PRESS is Chummer’s long-form publishing horizon: the future where approved Chummer material can become primers, handbooks, district guides, campaign books, convention modules, and creator-ready publications without duct-taping ten unrelated tools together.**

Short recaps are not enough.

Creators need books.
GMs need primers.
Organizers need campaign packets.
Living communities need season guides.
BLACK LEDGER needs city atlases.
KARMA FORGE needs rule-pack documentation.
Shadowcasters needs onboarding handbooks.

RUNBOOK PRESS is the long-form publishing lane.

Short recaps are not enough.

## The promise

**Turn approved Chummer truth into reusable books and modules.**

RUNBOOK PRESS helps produce:

- player primers
- GM handbooks
- district guides
- campaign books
- convention modules
- creator modules
- season books
- convention modules

It complements JACKPOINT.

JACKPOINT makes briefings, dossiers, and recaps.
RUNBOOK PRESS makes durable long-form works.

## What it feels like

An organizer finishes Seattle Season 01.

Chummer has:

- world ticks
- completed runs
- district changes
- faction summaries
- mission packets
- mission briefings
- runner legends
- GM notes
- campaign truth
- rule environment
- public-safe artifacts

RUNBOOK PRESS compiles:

```text
Seattle Season 01 Book

Sections:
- campaign overview
- player primer
- district state
- faction briefs
- timeline
- notable runs
- runner legends
- GM appendix
- rule environment
- open-run procedures
- creator credits
```

The book is not invented.

It is assembled from approved Chummer sources.

## What it should include

### Source-pack assembly

Long-form books should be built from:

- approved design/campaign/world packets
- player-safe recaps
- GM-only sections
- media artifacts
- rule environments
- district/faction state
- creator modules

### Editorial workflow

Support:

- outline
- draft
- review
- fact check
- spoiler pass
- layout
- export
- publication manifest
- revision
- retirement

### Publication manifest

Every book should know:

- source packets
- author/editor
- approval state
- visibility
- version
- compatible rulesets
- included packages
- export formats
- artifact refs

### Output formats

Potential outputs:

- PDF
- web guide
- print-ready packet
- Markdown
- Module archive
- campaign primer
- web article series
- video companion briefs

## What users want to know

### Is this for professional publishers only?

No. GMs, organizers, creators, and communities should all be able to use it at different levels.

### Does it replace JACKPOINT?

No. JACKPOINT is short-form; RUNBOOK PRESS is long-form.

### Will it make things up?

No. It must use approved source packets and preserve review state.

### Can it publish BLACK LEDGER seasons?

Yes. Season books are one of the strongest use cases.

### Can it document KARMA FORGE rule packs?

Yes. Rule-pack guides are a natural output.

## What it is not

RUNBOOK PRESS is not:

- one-click novel generator
- unreviewed AI book factory
- public spoiler leak
- replacement for creator approval
- renderer owning publication truth
- way to bypass source manifests

It is a long-form publishing pipeline.

## The first slice

The first slice should be:

**Campaign primer packet**

It should generate:

1. player primer
2. GM appendix
3. rule-environment summary
4. district/faction overview
5. source manifest
6. PDF/web export

Success looks like:

> A GM can onboard a new player with a polished campaign primer that stays aligned with the actual campaign state.

## The vision

Campaigns deserve books.

Communities deserve handbooks.

Creators deserve better than copy-paste chaos.

**RUNBOOK PRESS is where Chummer turns living campaign truth into long-form material that can be read, reused, taught, and published.**

# GHOSTWIRE — replay what really happened

**GHOSTWIRE is Chummer’s replay and after-action forensics horizon: the future where the table can reconstruct what happened, compare outcomes, and generate grounded after-action packets without rewriting history.**

Things go wrong.

A disputed combat turn.
A reconnect failure.
A rules confusion.
A player asks why a value changed.
The GM needs to know whether the session state is still trustworthy.

GHOSTWIRE exists for that moment.

## The promise

**When something matters, Chummer can show what happened.**

GHOSTWIRE uses receipts over time:

- event logs
- reducer-safe state changes
- explain packets
- reconnect receipts
- crash/recovery markers
- campaign ledger entries
- media receipts where available

It can reconstruct:

- timeline
- key changes
- contested moments
- before/after values
- safe state
- uncertain state
- what-if comparisons
- after-action reports

Without mutating canonical truth.

## What it feels like

A GM asks:

> “Why did this runner’s defense pool change?”

GHOSTWIRE shows:

```text
Timeline:
19:41 — rule environment unchanged
19:43 — rule triggered
19:44 — gear wireless state toggled
19:46 — reconnect occurred
19:46 — local pending edit discarded
19:47 — current value recalculated

Reason:
Defense changed because condition and wireless state interacted.
Reconnect did not alter the value.
```

The table can stop guessing.

## What it should include

### Replay timeline

A timeline of meaningful events:

- state change
- receipt
- conflict
- reconnect
- rule-environment change
- GM override
- support/crash event
- run resolution
- campaign/world consequence

### After-action report

A report that can show:

- what happened
- what changed
- what remains uncertain
- what was discarded
- what needs review
- what can be safely shared

### What-if comparison

Compare:

- before and after state
- alternate legal path
- different rule environment
- rollback candidate
- failed vs successful outcome

### Recovery memory

When Chummer crashes or reconnects:

- what was saved
- what was pending
- what is trustworthy
- what needs review
- next safe action exists

### Media artifacts

Optional:

- replay card
- after-action PDF
- narrated summary
- support evidence packet
- share-safe recap

## What users want to know

### Is this recording my game?

No. GHOSTWIRE is about receipt-backed Chummer state. Session media belongs to Table Pulse and requires consent.

### Can it settle rules arguments?

It can show what Chummer did and why. It does not replace the GM’s table authority.

### Can it help support?

Yes. It can produce better evidence packets.

### Can it create recaps?

Yes, but with source-backed events and approval.

### Can it change the past?

No. It reconstructs. It does not rewrite.

## What it is not

GHOSTWIRE is not:

- surveillance
- secret recording
- retroactive rule mutation
- GM override without trace
- invented recap
- VTT replay
- player discipline tool

It is forensics with receipts.

## The first slice

The first slice should be:

**After-action receipt packet for a disputed value**

It should show:

1. value before
2. events that changed it
3. receipts
4. current truth
5. uncertain/degraded state if any
6. share-safe report

Success looks like:

> A GM can answer “what happened?” without reconstructing the session from memory.

## The vision

Trust breaks when nobody can reconstruct the moment.

**GHOSTWIRE is where Chummer remembers the chain of events well enough to explain, recover, and move forward.**

# TABLE PULSE — split the live rail from the aftermath rail

**TABLE PULSE is a two-rail horizon: Table Pulse Live handles governed in-world heat and remote reactions, while Table Pulse Aftermath handles private post-session coaching without turning the table into a surveillance system.**

Every GM knows the feeling.

Something drifted.
One scene landed.
Another dragged.
One player carried the table.
Another disappeared.

The GM remembers the vibe but also needs a separate live pressure rail.

TABLE PULSE helps the GM handle both moments without pretending they are the same product.

Not live surveillance.
Not player scoring.
Not moderation truth.
Not discipline automation.

One live governed rail. One private coaching rail.

## The promise

**Give the GM live pressure tools and private insight without betraying the table.**

TABLE PULSE LIVE can help with:

- security, matrix, magic, astral, faction, law, media, or public pressure
- remote reaction mini-games
- recipient decision packets
- GM adjudication and aftermath follow-through

TABLE PULSE AFTERMATH can help with:

- pacing heat zones
- spotlight balance
- interruption patterns
- scene energy
- unresolved threads
- rules-dispute markers
- audience-facing recap suggestions
- GM-private coaching
- narrated debriefs

Only with explicit consent.

Only post-session by default for the aftermath rail.

Only as advice, not authority.

## What it feels like

During or after a session, the GM can enter one of two bounded flows.

TABLE PULSE LIVE says:

```text
Pressure packet:
- matrix heat crossed threshold
- a bounded remote reaction is available
- GM approval is still required before fallout becomes table truth
```

TABLE PULSE AFTERMATH says:

```text
Session pulse:
- rooftop chase had high engagement
- negotiation scene dragged for 22 minutes
- two players spoke less than 10% of the time after scene three
- one unresolved objective was never revisited

Suggestion:
Next run, open with a short player-facing recap and give the quietest player first meaningful choice.
```

Buttons:

- Generate player-safe recap
- Mark GM-only
- Ask for pacing suggestions
- Ignore this packet
- Delete media

The GM stays in control.

## What it should include

### Consent model

Before any audio/transcript/debrief lane:

- who consents
- what is recorded/uploaded
- what is analyzed
- who can see output
- retention
- delete path
- fallback if someone declines

### Post-session packet

Include:

- pacing summary
- spotlight balance
- scene markers
- unresolved threads
- player-safe suggestions
- GM-private coaching
- optional replay

### Manual markers

Even without recording:

- highlight
- rules dispute
- recap later
- scene dragged
- scene landed
- GM note

### GOD Observer

If used, it must be opt-in.

Possible modes:

- none
- manual markers
- post-session upload
- transcript assist
- live debrief assist with all-player consent

### Media output

Optional:

- coaching packet
- spoken summary
- GM-private video
- player-safe recap

## What users want to know

### Does it listen by default?

No.

### Can it score players?

No. That is forbidden.

### Can it moderate disputes?

No. It can help reflect; it does not decide.

### Can it generate recaps?

Yes, if source and consent allow it, and the GM approves.

### Can it help live?

The safe default is post-session. Any live mode must be explicit, consent-gated, and bounded.

## What it is not

TABLE PULSE is not:

- live surveillance
- default recording
- player scoring
- moderation truth
- session truth
- a GM replacement

It is not one single heat system.

It is two rails:

- `Table Pulse Live` for governed in-world heat, packets, remote reactions, and GM adjudication
- `Table Pulse Aftermath` for private coaching, recap, and debrief support

## The first slice

The first aftermath slice should be:

**Manual-marker post-session debrief**

It should let the GM:

1. mark moments during play
2. end session
3. see unresolved threads
4. draft player-safe recap
5. add private notes
6. publish or discard

No audio required.

Success looks like:

> A GM gets useful reflection without asking the table to trust a recorder yet.

The first live slice is different:

> A governed pressure packet crosses a threshold, a bounded remote reaction becomes available, and
> the GM still decides whether fallout becomes table truth.

## The vision

The best GMs improve because they can separate live pressure from private reflection.

**TABLE PULSE is where Chummer gives the GM a governed live pressure rail and a separate private aftermath rail without turning people into scores.**

# LOCAL CO-PROCESSOR — optional local-acceleration, hosted when needed

**LOCAL CO-PROCESSOR is Chummer’s optional local-acceleration horizon: the future where users with capable machines can run some explain, search, and media-assist work locally for speed, privacy, or cost — without making local compute mandatory.**

Some tasks are expensive.

Search.
Explain.
Preview.
Media-assist work.
Rule-environment projections.
Creator workflows.
Bulk media/help tasks.

A powerful local machine can help.

But Chummer cannot assume every user has one.

LOCAL CO-PROCESSOR is the optional path.

## The promise

**Use local power where available. Never require it.**

A creator with a strong desktop can opt into local acceleration.

A mobile-only player should still be able to play.

A GM on a modest laptop should still get the hosted path.

Local acceleration should improve:

- responsiveness
- privacy
- cost
- offline prep
- experimentation
- bulk search

But the same product flow must still work without it.

## What it feels like

A creator opens a heavy campaign primer job.

Chummer says:

```text
Local acceleration available.

This can speed up:
- source packet indexing
- preview rendering
- draft comparison
- search projection

Hosted fallback remains available.
No canonical truth depends on local acceleration.
```

The user can enable or ignore it.

If disabled, the workflow still works.

## What it should include

### Optional local worker

A local helper can support:

- search indexing
- preview rendering
- rule projection precompute
- media prep
- bulk export
- offline caching
- local-only drafts

### Hosted-first parity

Every major workflow must still have a hosted path.

Local should not become:

- required for Build Lab
- required for KARMA FORGE
- required for publication
- required for support
- required for Table Pulse
- required for open runs

### Receipts

Local execution should produce:

- what ran locally
- what was uploaded
- what stayed local
- what failed
- whether hosted fallback was used
- compatibility report

### Kill switch

Users must be able to:

- disable local acceleration
- clear local cache
- revoke local helper
- run hosted-only
- inspect local state

## What users want to know

### Do I need a powerful machine?

No. Local acceleration is optional.

### Will Chummer still work hosted-only?

Yes. Hosted-first parity is a hard rule.

### Is it more private?

It can be, for some workflows, if data stays local. Chummer must show exactly what stayed local.

### Is this for media generation?

Potentially for prep, preview, or local assist, but canonical media/publication still needs receipts.

### Can it help offline?

Yes, where workflows can be safely staged offline.

## What it is not

LOCAL CO-PROCESSOR is not:

- a hidden requirement
- a separate product tier by hardware
- local truth replacing engine truth
- uninspectable local AI
- a reason mobile users cannot participate
- support nightmare with no receipts

It is optional acceleration.

## The first slice

**Local preview/indexing helper for creator artifacts**

It should:

1. detect capable local machine
2. offer opt-in
3. run non-truth local indexing/preview
4. show receipt
5. fall back to hosted path
6. let user disable it

Success looks like:

> A creator gets faster preview work without Chummer depending on local compute.

## The vision

Chummer should be fast and private where possible, but fair and available everywhere.

**LOCAL CO-PROCESSOR is the horizon where local power becomes a bonus, never a gate.**

# COMMUNITY HUB — find the table, run the job, change the city

**COMMUNITY HUB is Chummer’s open-run and community-play horizon: the future where GMs can publish runs, players can apply with compatible runners, sessions can be scheduled and handed off cleanly, and the outcome can feed the living world.**

Finding a Shadowrun game is still too hard.

Rules live in Discord pins.
Character approvals happen in separate channels.
Scheduling happens in calendars or chat.
Meeting links appear at the last minute.
Publisher truth is not one place.

COMMUNITY HUB turns that into a product flow.

## The promise

**A GM opens a run. The right players find it. The table plays. The city remembers.**

It connects:

- BLACK LEDGER job packets
- open-run listings
- player applications
- runner dossiers
- quickstart runners
- community rule environments
- join policies
- scheduling receipts
- meeting handoff
- campaign pulse
- resolution reports
- seasonal honors
- newsreels
- world ticks

It is not a random LFG board.

It is Chummer’s structured run network.

## What it feels like

A new player opens Chummer.

They see:

```text
Open Runs This Week

Beginner-friendly extraction
Saturday 19:00
Voice required
Pregens allowed
Needs Matrix role
Uses Seattle Season 01 community rules
```

They click.

Chummer says:

```text
You can apply with:
- your own runner
- approved quickstart decker
- approved quickstart face

Your current runner:
- legal under base SR6
- blocked by this community environment until one gear choice is reviewed
```

The player applies with the quickstart decker.

The GM sees:

```text
Applicant:
new player
schedule fit: good
rule fit: pass
role fit: strong
table contract: acknowledged
```

The GM accepts.

Chummer schedules, hands off the Discord link, and tracks the run through closeout.

That is COMMUNITY HUB.

## What it should include

### Open-run listings

A listing should include:

- title
- spoiler-safe pitch
- source: custom, BLACK LEDGER, creator module, campaign run
- schedule
- seats
- needed roles
- rule environment
- beginner friendliness
- content notes
- voice/video/text
- platform handoff
- join policy
- observer policy
- GM reputation/honors where safe

### Join policies

GMs define:

- open auto-accept
- request-to-join
- invite-only
- waitlist
- organizer-curated
- beginner-friendly
- minimum/maximum advancement band
- required rule environment
- allowed quickstarts
- schedule rules
- content/safety acknowledgement
- consent/GOD Observer policy

### Player application preflight

Chummer checks:

- account state
- runner dossier
- rule environment
- role fit
- schedule fit
- table contract
- duplicate booking
- quickstart eligibility
- missing packages
- GM approval requirements

### Scheduling

Use Lunacal or another provider as scheduling projection.

Chummer owns:

- run plan
- roster
- accepted players
- scheduling receipt
- meeting handoff
- session status

### Meeting handoff

Support:

- Discord
- Teams
- generic URL
- VTT link

External tools host the meeting.
Chummer owns the run truth.

### Resolution

After play:

- GM files outcome
- players can give feedback
- BLACK LEDGER consumes result if applicable
- recap/newsreel generated
- reputation events recorded
- seasonal honors update

## What users want to know

### Is this just LFG?

No. It includes rule-environment preflight, runner applications, scheduling, table contract, roster truth, and run closeout.

### Does it replace Discord?

No. Chummer owns campaign logic. Discord can remain the community and meeting surface.

### Can new players join without a full desktop setup?

That is a core goal. Quickstart runners and mobile-first application paths should reduce the Windows-only chokepoint.

### Can GMs control who joins?

Yes. Join policies and application review are central.

### Can open runs affect BLACK LEDGER?

Yes, if the run is linked and the GM/organizer approves the resolution.

### Can reputation become toxic?

It must not. Use seasonal honors, typed event receipts, and no public shame boards.

## What it is not

COMMUNITY HUB is not:

- random matchmaking
- Discord-owned run truth
- Teams-owned roster truth
- VTT-owned consequence truth
- automatic recording
- public shame board
- pay-to-win ranking
- a table without GM authority

It is structured community play.

## The first slice

The first slice should be:

**Beginner-friendly open run**

It should:

1. publish one open run
2. show it on map/list
3. allow player application with quickstart runner
4. preflight rule environment
5. let GM accept/waitlist
6. schedule through Lunacal
7. reveal Discord/Teams handoff
8. prompt GM resolution
9. publish player-safe recap
10. record one seasonal honor event

Success looks like:

> A new player finds a run, joins safely, plays, and sees the result matter.

## The vision

Shadowrun communities already exist.

Chummer should not replace them.

It should give them structure.

**COMMUNITY HUB is where Chummer becomes the layer that turns job packets into tables, tables into outcomes, and outcomes into a living world.**
