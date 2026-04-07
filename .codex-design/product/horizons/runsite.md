# RUNSITE

## The problem

GMs spend too long describing spaces at the table, and players still misread compounds, clubs, hotels, museums, arcologies, and safehouses once the action starts. The pain is table-time churn: everyone keeps reconstructing the same spatial context from text, and the run loses momentum before the first move.

## What it would do

Chummer would publish explorable location packs linked to mission briefings.
That is the bounded product move: turn static location description into pre-run orientation, not live combat truth, not encounter adjudication, and not a VTT replacement.
RUNSITE is for briefing, planning, and spatial understanding before things go loud.

## Likely owners

* `chummer6-hub` owns publication, permissioning, and pack truth.
* `chummer6-media-factory` owns media generation, rendering, and asset delivery.
* `fleet` mirrors and verifies the canon but does not own the product truth for this horizon.

## LTD / tool posture

* `Crezlo Tours` - primary explorable-tour lane
* `AvoMap` - route and location visualization support
* `PeekShot` - preview/share-card adapter
* `Soundmadeseen` - optional narration layer
* `BrowserAct` - bounded operator automation and capture fallback

The LTD posture stays conservative: no new long-lived dependency is required to prove the lane, no tool may become source of truth, and every tool stays subordinate to published pack truth and permissioned delivery.

## What has to be true first

* clean media manifests
* permissioned publication links
* preview and embed receipts
* signed source trail for each pack
* reliable map and render adapters
* stable owner and permission boundaries for hosted publication

## Current state

The new vendor path makes this more plausible, but Chummer still needs a reliable permission model, a clear source trail, and dependable adapters before it should present RUNSITE as a real feature. It is still a horizon because the necessary foundations are not yet proven end to end.

## Eventual build path

1. Hub publishes the location-pack and mission-briefing entry points.
2. Media Factory generates the map, preview, and share artifacts from clean manifests.
3. The explorable pack opens from a briefing surface with permissioned access and receipt coverage.
4. Optional narration and route overlays are layered in only after the core pack path is stable.
5. Tool integrations remain adapters around the pack, never the owner of pack truth.

## Why it remains a horizon

RUNSITE stays a horizon until the product can prove that location packs are permissioned, traceable, and repeatable without hand-held operator repair. Until then it is a promising lane, not a shipped commitment.

## Flagship handoff gate

Do not hand RUNSITE to flagship status until one real location pack can be created, permissioned, rendered, previewed, and opened from a mission briefing with a complete provenance trail and preview/embed receipts, and the same flow succeeds on at least one desktop and one mobile proof path without manual operator patching.
