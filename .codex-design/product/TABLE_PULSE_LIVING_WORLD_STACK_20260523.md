# Table Pulse Living World Stack

Date: 2026-05-23

## Purpose

This document folds the recent Tibor design drops into one design-side product canon for
Chummer6. It is the product-layer summary above the queue rows:

- `m148` Table Pulse heat reaction
- `m149` living-world engagement loops
- `m150` opt-out and remote-reaction mini-game delta
- `m151` Table Pulse living-world V2 convergence
- `m152` living-world big redesign V3 surface layer

## Product Stack

### Layer 1: Table Pulse Live Core

Table Pulse Live is the live-session pressure and response layer.

It owns:

- heat domains and thresholds
- GM pulse policy
- recipient decision packets
- external notification gating
- GM adjudication
- Black Ledger public-safe consequence projection

Hard boundary:

- no outside action auto-applies to a live session

### Layer 1B: Table Pulse Aftermath

Table Pulse Aftermath is the private coaching and recap rail that stays separate from the live
pressure lane.

It owns:

- pacing and spotlight follow-through
- confusion and disengagement diagnostics
- GM-private recap and coaching packets
- optional narrated or player-safe aftermath artifacts
- consent, retention, and review posture for debrief outputs

Hard boundary:

- aftermath packets may inform the GM, but they do not become world truth, moderation truth, or
  player scoring

### Layer 2: Living World Engagement

Living World Engagement turns bounded receipts into between-session player and faction loops.

It owns:

- notification inbox and settings
- faction standing orders
- rumor market and intel hooks
- runner passport
- downtime micro-actions
- receipt-backed multichannel delivery

Hard boundary:

- this is a governed engagement layer, not autonomous simulation

### Layer 3: Opt-Out And Remote Reaction Mini-Games

This layer makes Table Pulse Live socially safe and playable.

It adds:

- GM opt-out defaults
- player mutes and notification preferences
- remote reaction mini-games
- suppression receipts
- stronger quiet-hours / anti-spam / consent proof

Hard boundary:

- remote reactions are mini-games and packets, not direct table mutation

### Layer 4: Living World V2 Control Surface

This is the convergence layer that makes the system feel designed instead of bolted together.

It adds:

- Pulse Director modes
- GM cockpit
- heat clocks and pressure economy
- AI steward suggestion fallback
- Black Ledger after-action projection
- BeHuman live-room bounds

Hard boundary:

- AI stewards may suggest, but never own table authority

### Layer 5: Big Redesign V3 Surface

This is the player-facing redesign layer.

It adds:

- Signal Deck
- stronger Passport framing
- faction role paths
- opposition clocks
- living newsroom framing
- clearer external-adapter boundaries

Hard boundary:

- media derives from receipts and never becomes truth by itself

## Split Rule

Table Pulse must stay explicit about its two rails:

- `Table Pulse Live` handles in-world heat, notifications, remote reactions, and GM adjudication
- `Table Pulse Aftermath` handles private coaching, recap, and debrief support

They may share receipts, policy, and continuity surfaces, but they should not be described as one
heat system.

## Ownership

### `chummer6-design`

- canon, claims, boundaries, product surfaces

### `chummer6-hub`

- GM cockpit, policy, adjudication, inbox, rumors, orders, projection, newsroom-facing truth

### `chummer6-mobile`

- PWA/mobile reaction surfaces, signal deck, passport surface, delivery interaction rails

### `executive-assistant`

- recipient decision packets
- AI steward suggestions
- rumor/intel explanation layer

### `fleet`

- privacy/rate-limit gates
- suppression proof
- readiness and final verdict receipts

## Non-Negotiables

- GM remains final authority
- private campaigns default silent
- notifications are opt-in
- external tools are adapters only
- no player-shaming rankings
- every action emits Chummer-owned receipts
- public Black Ledger projection requires public-safe GM-approved posture

## Design Reading Order

Read these together:

- [TABLE_PULSE_HEAT_REACTION_AUDIT_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/TABLE_PULSE_HEAT_REACTION_AUDIT_20260523.md)
- [LIVING_WORLD_ENGAGEMENT_AUDIT_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/LIVING_WORLD_ENGAGEMENT_AUDIT_20260523.md)
- [TABLE_PULSE_OPTOUT_REMOTE_REACTION_AUDIT_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/TABLE_PULSE_OPTOUT_REMOTE_REACTION_AUDIT_20260523.md)
- [TABLE_PULSE_LIVING_WORLD_V2_AUDIT_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/TABLE_PULSE_LIVING_WORLD_V2_AUDIT_20260523.md)
- [LIVING_WORLD_BIG_REDESIGN_V3_AUDIT_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/LIVING_WORLD_BIG_REDESIGN_V3_AUDIT_20260523.md)
- [TABLE_PULSE_LIVING_WORLD_DRAMA6_BRIEF_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/TABLE_PULSE_LIVING_WORLD_DRAMA6_BRIEF_20260523.md)

This file is the short product canon above those detailed intake documents.
