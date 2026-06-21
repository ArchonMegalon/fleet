# Table Pulse Living World Drama Brief

Date: 2026-05-23

## Use

This file is the generator-facing briefing packet for dramatic product documentation.
It is written so a documentation skill or narrative doc tool can turn the Chummer6
Table Pulse and Living World stack into a cool but accurate product explainer without
inventing authority that the product does not actually have.

## One-Line Pitch

Chummer6 turns live table pressure, between-session faction motion, and public-safe
world fallout into one governed play loop where the GM stays in charge and every
meaningful action leaves a receipt.

## Three-Line Elevator

At the table, Table Pulse Live converts moments of heat into bounded reaction packets instead
of free-floating chaos.

Between sessions, Living World systems turn those packets into rumors, orders, inbox
items, passports, mini-actions, and public-safe fallout that give players reasons to
come back.

Across every surface, the rule is simple: AI may suggest, media may dramatize, but only
governed Chummer receipts and GM approval become truth.

Table Pulse Aftermath is the separate private coaching rail. It is not the same thing as the live
heat and reaction loop, even when both rails share consent, receipt, and follow-through posture.

## Audience Fantasy

- GM fantasy: "I stay in control while the system makes the world feel alive."
- Player fantasy: "My squad matters even when we are not in the room."
- Faction fantasy: "The city remembers what we did and pushes back."
- Viewer fantasy: "This world feels in motion, but it is not fake simulation theater."

## Stack In One Sentence Each

- `m148` Table Pulse Live heat reaction: live-session pressure becomes bounded packets,
  notifications, adjudication, and public-safe consequence signals.
- `m149` living-world engagement loops: those packets become inbox, rumors, orders,
  passport progress, and downtime hooks.
- `m150` opt-out and remote reaction delta: the system becomes socially safe, consentful,
  rate-limited, and playable outside the room.
- `m151` V2 convergence: the whole stack becomes a designed command system with Pulse
  Director, GM cockpit, pressure economy, and after-action projection.
- `m152` big redesign V3: the player-facing layer becomes a flagship surface with Signal
  Deck, stronger Passport framing, faction role paths, opposition clocks, and living
  newsroom framing.

## Hero Surfaces

### Signal Deck

- what it is: the fast player-facing action board
- feeling: urgent, readable, street-level, tactical
- must show: current signals, consequences, response lanes, and world pressure
- must never imply: automatic world authority without receipts

### Runner Passport

- what it is: the player identity and momentum surface
- feeling: earned, personal, city-connected
- must show: standing, path, role cues, and session-to-session continuity
- must never imply: gamified shame ladders or public ranking humiliation

### GM Cockpit

- what it is: the authority surface for pulse policy, adjudication, and approvals
- feeling: calm, legible, sovereign
- must show: thresholds, packets, overrides, quiet-hours, opt-outs, proofs
- must never imply: AI is making the final call

### Living Newsroom

- what it is: the public-safe consequence layer
- feeling: cinematic, reactive, receipt-backed
- must show: fallout, faction movement, public-safe projection, after-action framing
- must never imply: media invented the event by itself

## Core Dramatic Beats

### Beat 1: Spark

- trigger: a live session raises heat
- payload: a governed pulse packet is created
- proof: threshold crossing, GM policy, recipient logic

### Beat 2: Reach

- trigger: the packet is allowed to leave the table
- payload: inbox items, notifications, mini-games, rumors, or orders
- proof: consent, privacy, quiet-hours, rate-limit receipts

### Beat 3: Response

- trigger: players, factions, or GMs react
- payload: mini-actions, adjudication, role-path movement, pressure changes
- proof: receipt chain and GM authority gate

### Beat 4: Fallout

- trigger: enough validated response accumulates
- payload: Black Ledger / newsroom / after-action projection
- proof: public-safe approval and consequence receipts

## Example User Stories

### GM Story

The GM sees rising heat during a run, lets the system form a bounded reaction packet,
approves a quiet-hours-safe delivery to the right players, adjudicates one remote
reaction mini-game, and later approves a public-safe fallout summary for the world map.

### Player Story

A player gets a muted-but-important Signal Deck prompt after the session, chooses a
remote reaction mini-game, advances Passport standing, and later sees the city newsroom
reflect the outcome without the system leaking private table truth.

### Faction Story

A faction contact receives a governed standing-order update, reacts through rumor and
pressure lanes, and nudges the opposition clock in a way the newsroom can later present
without exposing hidden campaign state.

## Boundaries And Truth Rules

- GM is final authority
- private campaigns default silent
- opt-in beats opt-out only where the player explicitly said yes
- mini-games are reactions, not direct table mutation
- AI suggestions are advisory only
- BeHuman and Answerly are adapter layers, not system truth owners
- public projection requires a public-safe posture
- receipts outrank vibes, headlines, and summaries

## Required Visual Language

- control room, signal board, pressure map, newsroom desk, passport dossier
- sharp state transitions: calm, spike, review, release, fallout
- dense but readable information hierarchy
- no bland dashboard language
- no generic "notification center" framing

## Recommended Documentation Sections

- why this exists
- what changed from static campaign tooling
- the five-layer stack
- the three authority rules
- the four dramatic beats
- hero surfaces
- example player / GM / faction journeys
- privacy and consent guarantees
- Black Ledger and newsroom truth boundaries
- implementation ownership across design, hub, mobile, EA, and fleet

## Artifact Checklist For A Cool Doc

- one flagship headline
- one architecture diagram of the five layers
- one GM journey
- one player journey
- one public-fallout journey
- one truth-boundary callout box
- one "what AI may do / may not do" table
- one "receipt flow" sequence
- one "why this is not fake simulation" explanation

## Input Sources

- [TABLE_PULSE_LIVING_WORLD_STACK_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/TABLE_PULSE_LIVING_WORLD_STACK_20260523.md)
- [TABLE_PULSE_HEAT_REACTION_AUDIT_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/TABLE_PULSE_HEAT_REACTION_AUDIT_20260523.md)
- [LIVING_WORLD_ENGAGEMENT_AUDIT_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/LIVING_WORLD_ENGAGEMENT_AUDIT_20260523.md)
- [TABLE_PULSE_OPTOUT_REMOTE_REACTION_AUDIT_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/TABLE_PULSE_OPTOUT_REMOTE_REACTION_AUDIT_20260523.md)
- [TABLE_PULSE_LIVING_WORLD_V2_AUDIT_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/TABLE_PULSE_LIVING_WORLD_V2_AUDIT_20260523.md)
- [LIVING_WORLD_BIG_REDESIGN_V3_AUDIT_20260523.md](/docker/chummercomplete/chummer6-design/products/chummer/LIVING_WORLD_BIG_REDESIGN_V3_AUDIT_20260523.md)

## Output Constraint

Any generated documentation must preserve this rule:

Only receipts and GM-approved public-safe projections count as world truth. Everything
else is presentation, guidance, or dramatization.
