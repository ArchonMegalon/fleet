# Hedy AI in Table Pulse Aftermath

## Purpose

Define the bounded role `hedy.ai` may play inside `TABLE PULSE AFTERMATH`.

This is not a general AI-provider promotion.
It is a narrow design for post-session coaching packets where `hedy.ai` appears to fit the
session-structure and debrief side of `Table Pulse Aftermath` better than the deeper
social-dynamics interpretation side.

## Why it fits

`TABLE PULSE AFTERMATH` needs two different kinds of help:

1. structural session digestion
2. coaching interpretation

Structural digestion means:

* finding likely scene or topic shifts
* extracting highlights and unresolved hooks
* surfacing candidate pacing drags
* turning a long transcript into a compact GM debrief packet

Coaching interpretation means:

* spotlight balance judgment
* interpersonal friction interpretation
* engagement diagnosis
* bounded next-session guidance

`hedy.ai` fits the first layer better than the second.
So the product posture should treat it as a conversation-structure and debrief helper, not as the canonical coaching brain.

## Product role

Inside `TABLE PULSE AFTERMATH`, `hedy.ai` is a bounded secondary lane for:

* transcript-to-session-outline extraction
* highlight and action-item extraction
* unresolved-thread and callback candidate extraction
* GM-facing debrief prompt generation
* short post-session recap drafts

It is not the primary lane for:

* player psychology claims
* interpersonal judgment
* moderation claims
* discipline recommendations
* rules adjudication

`Nonverbia` remains the primary social-dynamics analysis lane.
`hedy.ai` should feed that lane or run alongside it as a structural counterpart.

## Preferred output types

`hedy.ai` should be asked for bounded artifacts only:

* `session_outline`
  scene/topic blocks with timestamps or sequence offsets
* `highlight_digest`
  what clearly landed, what stalled, what stayed unresolved
* `gm_debrief_prompts`
  short reflective questions for the GM
* `player_safe_recap_draft`
  optional share-safe neutral recap with no player scoring language

All outputs should be short, structured, and receipt-bearing.

## Recommended pipeline

1. Chummer-owned media or transcript prep happens first.
2. Consent and retention policy is checked before any provider call.
3. `hedy.ai` receives a prepared transcript or transcript slices, not raw unrestricted workspace access.
4. `hedy.ai` returns a bounded structural digest.
5. Chummer-owned orchestration merges that digest with:
   * replay refs when available
   * scene/run metadata when available
   * optional `Nonverbia` coaching analysis
6. Chummer emits a `TABLE PULSE AFTERMATH` packet with provider receipts and confidence notes.

## Safe request shapes

Good `hedy.ai` request shapes:

* "Split this post-session transcript into likely scene/topic phases."
* "List the strongest highlights, dropped threads, and likely pacing stalls."
* "Draft 5 neutral GM debrief questions based on this session transcript."
* "Produce a player-safe recap draft with no judgmental language."

Bad request shapes:

* "Rank the players."
* "Tell us who was the problem."
* "Decide whether someone behaved badly."
* "Judge whether the GM was fair."
* "Infer hidden motives or diagnose people."

## Hard boundaries

`hedy.ai` in Chummer must stay:

* opt-in
* post-session only
* transcript-first where possible
* bounded to coaching support, never moderation truth
* separate from canonical session truth
* separate from discipline, sanctions, or player scoring

The product must not use `hedy.ai` for:

* live whisper coaching during the session
* covert participant monitoring
* automated social scoring
* canonical event-memory generation
* trust or safety enforcement decisions

## Data minimization posture

Default data posture:

* prefer transcript over raw audio/video
* prefer sliced excerpts over entire archives when enough
* strip direct identifiers when the packet goal does not need them
* retain only the Chummer-owned output packet and provider receipt by default
* keep provider-side retention disabled or minimized where contractually possible

## Ownership

Primary owners:

* `chummer6-hub`
  consent, routing, packet orchestration, and policy enforcement
* `chummer6-media-factory`
  transcript preparation, packet rendering, and optional recap-media transforms
* `chummer6-design`
  prompt boundaries, packet semantics, and rollout authority

## Acceptance bar before promotion

Before `hedy.ai` becomes an approved active `TABLE PULSE AFTERMATH` lane, Chummer should prove:

* it materially improves transcript-to-outline quality or recap usefulness
* it stays within non-judgmental, non-surveillance boundaries
* outputs are stable enough to support operator review
* player-safe recap drafts remain share-safe
* the lane can be disabled without losing canonical session or replay truth

## Rollout posture

Current posture should be:

* `Bounded`
* `table-pulse only`
* `operator-reviewed or GM-preview only`
* `never sole authority`

Recommended rollout phases:

1. offline internal eval on consented transcripts
2. GM-only preview packets
3. optional player-safe recap draft
4. broader activation only if receipts show clear value and low policy risk

## Success signals

Good signals:

* GMs say the packet shortened post-session note-taking
* scene/topic boundaries are usually useful without manual rewrite
* recap drafts require light editing rather than full replacement
* the lane adds structure without inventing dramatic claims

Bad signals:

* personality or blame language appears
* pacing claims are vague and repetitive
* recap drafts drift into moderation or scoring language
* operators cannot explain why the packet said what it said

## Canonical decision

`hedy.ai` is a good fit for `TABLE PULSE AFTERMATH` only as a bounded session-structure and debrief helper.
It should complement `Nonverbia`, not replace it, and it must stay firmly outside live surveillance, player scoring, moderation truth, and canonical session memory.
