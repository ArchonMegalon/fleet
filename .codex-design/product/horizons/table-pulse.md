# TABLE PULSE

## The table pain

After a session, the GM often has fragments instead of proof: pacing felt off, one player may have been crowded out, an interruption pattern may have derailed the room, and the actual scene-by-scene pulse is hard to reconstruct without replay work that nobody wants to do by hand.

## The bounded product move

TABLE PULSE is a post-session coaching lane, not a live table-monitoring system.
The bounded move is to turn consented session media into opt-in reflection notes about pacing, spotlight balance, engagement, and interruptions, with optional narrated summaries and share-safe coaching packets.

It is intentionally limited to after-action reflection.
It must not become live surveillance, player scoring, moderation truth, discipline automation, or canonical session truth.

## Owning repos

* `chummer6-design` owns the horizon canon, registry truth, and the boundary language that keeps this lane parked until the rest of the product is ready.
* `chummer6-hub` owns the consent, upload, account, and sharing surface that would front the coaching workflow.
* `chummer6-media-factory` owns the bounded media processing and artifact generation path behind that surface.

Fleet may mirror, route, and verify the lane, but it does not own the product truth for it.

## LTD and tool posture

TABLE PULSE should only use owned LTDs through bounded adapters, never as a truth source.

Current posture:

* `Nonverbia` is the primary coaching and social-dynamics analysis lane.
* `hedy.ai` is the bounded transcript-structure and GM debrief helper lane.
* `Soundmadeseen` is the optional narrated coaching-summary lane.
* `Unmixr AI` remains a bounded candidate voice lane until the media path proves it.
* `MarkupGo` supports coaching-packet rendering.
* `PeekShot` supports preview and share-safe summary cards.

The tools may assist, summarize, render, or project. They may not become canonical session truth, moderation truth, or the policy engine for the lane.

## Dependency foundations

This horizon depends on a few foundations being boringly reliable first:

* explicit consent and upload policy
* post-session-only analysis rules
* privacy and retention rules for coaching media
* share-safe summary and preview rules
* replay and receipt references where available
* Hub-owned identity and sharing truth
* Media Factory adapters that keep tool execution bounded and inspectable

If those foundations are not already proven, the lane stays parked.

## Current state

Nothing here is live product behavior yet.
This file exists as a disciplined future lane definition and a mirror for the canonical horizon registry, not as evidence that the workflow is safe to ship.

## Eventual build path

The likely build path is:

1. Hub captures consent, upload, and share intent.
2. Media Factory ingests the session artifact and runs bounded analysis.
3. The selected LTDs generate coaching notes, digest structure, and optional narration.
4. Hub presents the post-session review packet back to the GM.
5. Later waves can add richer summaries, better share cards, and tighter receipt linking once the safety boundaries are already proven.

That path remains intentionally post-session only.

## Why it remains a horizon

TABLE PULSE remains a horizon because the product still needs end-to-end proof that consent, privacy, retention, and non-truth boundaries hold under real usage.
Until Chummer can demonstrate that the workflow stays separate from moderation and rules truth, this cannot graduate from future lane to product promise.

## Flagship handoff gate

Promote this lane only when all of the following are true in a real end-to-end run:

* explicit user consent is captured before upload
* only post-session media can enter the pipeline
* retention and redaction rules are enforced by the owning system
* the coaching packet is clearly labeled as reflection, not truth
* share-safe output is produced without exposing raw sensitive media
* the tool chain stays behind bounded adapters and does not leak raw truth back into the product surface
* one complete session can be replayed from receipt to summary without manual patching

If any one of those gates fails, TABLE PULSE stays parked as a horizon.
