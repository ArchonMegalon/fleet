# Structured video and narrated media model

## Purpose

Project Chummer already has image, document, recap, runsite, and narrated-media posture, but it does not yet have a first-class model for structured presenter video, multilingual walkthrough video, or video-shaped companion artifacts.

This document closes that gap.

It defines how Chummer should use owned LTDs such as `vidBoard`, `Soundmadeseen`, `MarkupGo`, `PeekShot`, `First Book ai`, `Documentation.AI`, `Mootion`, `Unmixr AI`, `AvoMap`, `Crezlo Tours`, `hedy.ai`, and `Nonverbia` to produce polished media with real wow-factor without letting any vendor become product truth.

## Current audit

The current design is strong on guardrails and weak on one specific thing: a concrete video lane.

What is already strong:
- `JACKPOINT` has dossiers, recaps, briefings, evidence rooms, and creator packs.
- `RUNSITE` has explorable location packs, route overlays, and optional narration.
- `RUNBOOK PRESS` has long-form primers, guides, and modules.
- `TABLE PULSE AFTERMATH` has bounded post-session coaching and recap posture, while `TABLE PULSE LIVE` remains the separate in-world heat and reaction rail.
- `chummer6-media-factory` already owns render execution, manifests, provider adapters, previews, and media receipts.

What is still missing:
- no single machine-readable workflow registry for source pack -> script -> approval -> render -> preview -> publish -> feedback
- no first-class artifact-factory recipe registry that normalizes primary lane, fallback lane, approval path, and publication surfaces together
- no public proof shelf that makes the video/document/audio artifact factory obvious as a first-party product lane

## Core rule

Structured video and narrated media are downstream artifacts.

They may feel polished, cinematic, and human-friendly.
They may not become canonical rules truth, canonical session truth, canonical support truth, canonical approval truth, or canonical publication truth.

The Chummer-owned truth remains in:
- contracts
- manifests
- publication refs
- source packs
- support/case state
- campaign/dossier state
- release/install/update state

Video is a presentation lane.
It is not the source-of-truth lane.

## Proposed ownership split

### `chummer6-design`
Owns:
- policy
- workflow semantics
- artifact-family definitions
- approval and safety posture
- rollout authority

### `chummer6-hub`
Owns:
- orchestration
- user- and campaign-facing triggers
- consent and privacy gating
- publication routing
- support/help/account distribution surfaces
- operator review and approval UX

### `chummer6-media-factory`
Owns:
- `IVideoRenderAdapter` execution
- prepared render payloads
- provider receipts
- preview generation
- lifecycle and retention execution
- switchable provider control

### `chummer6-hub-registry`
Owns:
- artifact references
- publication refs
- compatibility metadata
- locale/ref/version linkage
- published-asset identity

### `executive-assistant`
Owns:
- vendor/account stewardship
- operator-side helper workflows
- BrowserAct fallback automation where vendor APIs are weak
- no canonical product meaning

## Tool posture

### Promoted
- `vidBoard` - structured presenter-video and multilingual walkthrough lane
- `Soundmadeseen` - narrated audio/video companion lane
- `MarkupGo` - document/render sibling lane for packet and PDF parity
- `PeekShot` - preview/share-card lane
- `First Book ai` - long-form blueprint and script-outline helper
- `Documentation.AI` - downstream help/guide projection from approved scripts and manifests

### Bounded
- `Mootion` - motion-only b-roll and short animated support lane
- `Unmixr AI` - candidate dubbing and voice lane until proven
- `hedy.ai` - transcript structure / debrief helper for `TABLE PULSE AFTERMATH`, not a live or canonical lane
- `Nonverbia` - social-dynamics and coaching analysis lane for `TABLE PULSE AFTERMATH`, not publication truth
- `AvoMap` - route and location visualization lane
- `Crezlo Tours` - explorable tour lane
- `BrowserAct` - operator fallback for upload, export, publishing, or receipt capture when vendor APIs are weak or absent
- `ApproveThis` - approval bridge, not policy truth
- `MetaSurvey` - usefulness and follow-up signal collection, not publication truth

## New artifact families

Chummer should make video a first-class artifact family instead of treating it as a one-off provider side effect.

Add these artifact kinds:
- `public_explainer_video`
- `release_explainer_video`
- `support_closure_video`
- `build_explain_companion_video`
- `campaign_primer_video`
- `mission_brief_video`
- `runsite_orientation_video`
- `creator_promo_video`
- `player_safe_recap_video`
- `gm_private_debrief_video`
- `artifact_teaser_video`

The machine-readable brief and workflow canon for these families now lives beside this document in:
- `PUBLIC_VIDEO_BRIEFS.yaml`
- `MEDIA_ARTIFACT_RECIPE_REGISTRY.yaml`

Each published video artifact should carry:
- source pack ref or script ref
- locale
- approval state
- preview asset ref
- caption asset ref
- provider receipt ref
- publication ref
- retention policy
- compatibility or audience label where relevant

## Default render rules

### General
- no vendor watermarks on promoted artifacts
- no provider names in public-facing output
- captions required for every public or support-facing video
- preview required before publication
- every video has a sibling preview card
- every public/help/support video has a document or page sibling when the user needs inspectable detail

### Runsite orientation surfaces
- `runsite_orientation_video` is preview-safe host mode, not route or tactical authority
- every runsite orientation launch must keep inspectable route, map, or tour siblings visible before playback and reachable during playback
- approved runsite pack and route summary truth outrank host narration whenever wording drifts
- runsite orientation clips may not claim live state, combat authority, or hidden tactical instructions that are absent from the approved pack or route summary

### Text and truth
- public or help videos may only speak from approved scripts or approved manifest-derived summaries
- exact text that matters for trust should be post-reviewed before publication
- no improvisational factual claims about rules, support status, release compatibility, or pricing

### Avatar policy
- avatar-presenter mode is allowed for public explainers, support walkthroughs, campaign primers, and mission briefings
- faceless mode is preferred when the content is dense, documentary, or potentially uncanny with a presenter
- do not synthesize a real player, GM, or public figure without explicit consent and a clear reason
- player-safe recap video should default to faceless or neutral presenter mode, not a pseudo-human reenactment of the table

### Localization
- `en-US` remains the script-source base when an approved translated source is not available
- required first-wave locales match the product locale set: `en-US`, `de-DE`, `fr-FR`, `ja-JP`, `pt-BR`, `zh-CN`
- localized captions are required whenever localized voiceover is shipped
- locale review remains required for public/support-facing publication

## Default workflow

1. Chummer-owned source selection
   - campaign pack
   - dossier brief
   - release note bundle
   - support resolution summary
   - primer pack
   - runsite pack
   - post-session recap draft

2. Script or storyboard preparation
   - direct manifest-derived summary when possible
   - `First Book ai` only for blueprint or storyboard help
   - `Documentation.AI` only for downstream guide/help projection
   - no vendor gets unrestricted workspace access

3. Approval checkpoint
   - `ApproveThis` or Chummer-owned approval UI
   - public-facing, support-facing, and shared campaign-facing outputs must not auto-publish without approval

4. Media render package
   - `chummer6-hub` composes a prepared request
   - `chummer6-media-factory` chooses the provider adapter privately
   - `vidBoard` is the preferred presenter-video adapter for the structured lane
   - `Soundmadeseen`, `Mootion`, `Unmixr AI`, `AvoMap`, or `Crezlo Tours` may contribute bounded sibling outputs where the workflow allows them

5. Preview and sibling artifact generation
   - `PeekShot` preview card
   - `MarkupGo` packet or PDF sibling when appropriate
   - captions and transcript assets linked

6. Publication
   - `chummer6-hub-registry` stores artifact ref and publication metadata
   - `chummer6-hub` exposes the result in the right user surface

7. Feedback and usefulness loop
   - `MetaSurvey` or Chummer-owned reaction capture may ask whether the video actually helped
   - usefulness never replaces publication truth or support truth

## Where this should immediately show up

### Public and help surfaces
- release explainer videos
- "what changed" videos
- first-run / claim / install help clips
- language-matched support explainers

### Campaign and GM surfaces
- mission briefing videos
- campaign primer videos
- runsite orientation clips
- pre-session "what changed" briefings

### Build and Explain surfaces
- compare companions that summarize anchored deltas from approved explain packets
- import companions that restate bounded-loss or landed-success receipts without hiding repair steps
- blocker companions that restate inspectable blocker receipts and next-step actions

These lanes stay subordinate to inspectable engine truth:
- companion narration may cite packet anchors
- companion narration may not replace packet inspection
- approval may permit publication, but it may not authorize unanchored rules claims
- every rendered companion must preserve the exact packet revision, rule-environment identity, and approval scope it summarizes
- if revision identity, anchor scope, or approval scope cannot be shown honestly, the launch surface must fail closed to the packet, anchor sheet, or localized text fallback instead of pretending the narration is enough

### Creator and publication surfaces
- dossier trailer videos
- campaign primer teaser videos
- artifact teaser clips
- module and convention pack explainers

### Table Pulse surfaces
Allowed:
- player-safe recap video from approved recap draft
- GM-private debrief video from approved coaching packet

Not allowed:
- live whisper coaching
- live surveillance
- player ranking or discipline clips
- canonical event reconstruction by video alone

## Acceptance bar before promotion

Before `vidBoard` or any sibling lane becomes a promoted active route, Chummer should prove:
- the artifacts feel visibly more polished than static-only output for the same workflow
- the script and evidence path survive from Chummer truth into the published asset
- localization stays intelligible in the shipping locales
- the preview/sibling packet makes the result inspectable rather than theatrical
- the lane can be killed without breaking canonical truth or user recovery
- the output feels like Chummer and not like a random generic SaaS avatar ad

## Recommended rollout order

### P0 - policy and adapter discipline
- classify `vidBoard` in the tool inventory and capability map
- add video artifact kinds
- add a machine-readable video brief file
- add media-factory adapter family signoff for structured presenter video

### P1 - low-risk public utility
- release explainer videos
- install/update/support walkthroughs
- public guide companion explainers

### P2 - campaign wow-factor
- campaign primer videos
- mission briefing videos
- runsite orientation clips

### P3 - creator/publication wow-factor
- teaser clips
- dossier trailers
- artifact launch bundles

### P4 - bounded recap video
- player-safe recap video
- GM-private debrief video

## What this should not become

This model is not permission to flood Chummer with synthetic talking heads.

If every surface becomes an avatar video, the product gets cheaper, noisier, and less trustworthy.

The goal is:
- one polished video where it materially reduces friction
- a trusted sibling document/page where inspectability matters
- a clear evidence path
- strong localization leverage
- real wow-factor without surrendering product meaning
