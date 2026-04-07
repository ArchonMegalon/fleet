# JACKPOINT

## The table pain

Players and GMs want dossiers, recaps, primers, narrated briefings, evidence rooms, and shareable cards after a session.
The pain is that most content tools either invent details, lose provenance while reformatting, or force the table to rebuild the story by hand before anything can be trusted.
If the artifact cannot preserve where the facts came from, it is not helping the table.

## The bounded product move

JACKPOINT would take approved session material and turn it into dossiers, recaps, narrated briefings, evidence rooms, share cards, and creator packs.
The move is deliberately narrow: preserve provenance and approval while producing short-to-medium-form artifacts, not a full book pipeline, a campaign engine, or a general publishing studio.
It is a publishing lane for approved truth, not a replacement for the core rules or for long-form books.

## Likely owning repos

* `chummer6-hub`
* `chummer6-hub-registry`
* `chummer6-media-factory`

These repos own the product surface. Fleet may mirror execution and evidence around them, but it does not own the artifact truth.

## LTD/tool posture

* `MarkupGo` - document/render adapter lane
* `Soundmadeseen` - narrated recap and briefing media lane
* `Unmixr AI` - candidate voice lane until proven
* `PeekShot` - preview/share-card adapter
* `Documentation.AI` - downstream docs/help projection
* `Paperguide` - cited grounding helper
* `Mootion` - bounded video support
* `First Book ai` - bounded overflow support when the artifact lane needs long-form carryover

These tools may help render, narrate, preview, cite, or carry bounded overflow.
They do not decide approval, source classification, or release truth.
No owned LTD or tool helper may become the source of truth for the artifact chain.

## Dependency foundations

Before JACKPOINT can be a flagship lane, these foundations have to exist and stay boring under stress:

* a fact trail that survives formatting, narration, and preview generation
* explicit approval states
* source classification that survives export and publication
* registry and media working together cleanly
* reliable publication workflows
* reproducible outputs from the same approved session record

## Current state

Chummer can already describe these outputs, but it does not yet prove the full chain end to end.
The current gap is not whether the artifacts are desirable; it is whether approved session truth can survive writing, narration, preview generation, and publication without human repair.
Until that chain is reliable, JACKPOINT remains a horizon instead of a shipped promise.

## Eventual build path

1. Prove approved-session intake, source classification, and approval state capture in `chummer6-hub`.
2. Wire registry-owned artifact metadata and publication state in `chummer6-hub-registry`.
3. Add render, preview, narration, and bounded video flows in `chummer6-media-factory`.
4. Keep downstream docs and help projections as derived outputs only.
5. Promote the lane only after one complete approved-session slice survives all projections without fact drift.

## Why it is still a horizon

This remains a horizon because the product still lacks the trustworthy chain from approved session material to the full artifact set.
Until provenance survives formatting, narration, previews, and publication without repair, JACKPOINT would add another place to lose the facts instead of a reliable publishing lane.

## Flagship handoff gate

JACKPOINT becomes flagship-ready only when one release-candidate session packet can move through the primary path and:

* produce a dossier, recap, narrated briefing, and shareable artifact set from the same approved source
* preserve citations, provenance, and approval state across render, narration, preview, and publication
* classify the source trail correctly from intake through publish
* regenerate the same outputs after a failed preview or render without changing meaning
* complete the flow with the owning repos and release metrics stable enough that the lane can be handed off as a flagship surface, not a speculative horizon
