# GHOSTWIRE

## The problem

Table pain shows up when the live session is over and we still cannot reconstruct what actually happened, why it happened, or which parts are still trustworthy.

## Bounded product move

Chummer would support replay, after-action review, and forensics packets built from receipts over time.
This is intentionally narrow: it is about post-hoc reconstruction, not rewriting canonical session truth.
The product should be able to show what happened, what remains trustworthy, and the next safe move after an incident or recovery event.

## Owning repos

* `chummer6-core`
* `chummer6-mobile`
* `chummer6-hub`
* `chummer6-media-factory`

This is a cross-repo move; no single repo can finish it without the others.

## LTD / tool posture

* `PeekShot` - preview/share-safe replay surfaces
* `Soundmadeseen` - narrated after-action recap support
* `MarkupGo` - bounded report rendering
* `Mootion` - bounded replay/video experiments
* `Paperguide` - cited reconstruction helper

These tools are downstream surfaces, not truth sources.
The LTD posture stays receipt-first, bounded, and preview-safe until the reconstruction chain is proven.

## What has to be true first

* append-only reducer-safe ledger truth
* explain provenance canon
* runtime bundle receipts
* media-side receipt capture for after-action outputs
* degraded-state receipts that survive crash, reconnect, and restore paths

## Current state

GHOSTWIRE is not a product capability yet.
Today it is a horizon because the system can describe replay in the abstract, but cannot yet prove that every reconstruction is grounded in canonical receipts and reducer-safe state.

## Eventual build path

The path to product is: capture receipts, lock down provenance, prove reducer-safe replay, then add bounded replay and after-action views on top.
Only after the foundation is stable should the richer recovery, narration, and media outputs become customer-facing.

## Why it is not ready yet

Replay is only safe when reconstruction is receipt-backed and reducer-safe.
Until Chummer can prove that after-action views stay grounded in canonical truth rather than retrospective invention, GHOSTWIRE remains a horizon instead of product truth.

## Flagship handoff gate

Ship this only when a full incident can be replayed end-to-end from receipts, the reconstructed view matches canonical state, degraded recovery survives crash and restore, and at least one flagship surface can present the result without hand-editing or guesswork.
