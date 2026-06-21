# ADR-0016: structured presenter-video lane behind media-factory adapters

## Status
Proposed

## Context

Project Chummer already has:
- narrated audio posture
- bounded video posture
- document rendering posture
- share-card posture
- horizon-level media ambitions around `JACKPOINT`, `RUNSITE`, `RUNBOOK PRESS`, and later `TABLE PULSE AFTERMATH`

But the current canon does not yet define a first-class presenter-video lane for:
- multilingual campaign primers
- mission brief videos
- public release explainers
- support closure videos
- creator promo videos

At the same time, the owned LTD inventory now includes `vidBoard`, which is a strong fit for structured avatar/faceless video from approved text, URL, or document inputs.

## Decision

Project Chummer should recognize a new bounded but promoted media lane:

`vidBoard` -> structured presenter-video and multilingual walkthrough lane

This lane must sit behind `chummer6-media-factory` adapters and Chummer-owned manifests.

It may be used for:
- public release explainers
- campaign primers
- mission briefings
- runsite orientation clips
- support closure explainers
- creator promo videos
- later, bounded player-safe recap or GM-private debrief video only after stricter guardrail proof

It may not be used for:
- canonical rules truth
- canonical session truth
- live surveillance or in-session whisper coaching
- player scoring or discipline outputs
- direct client-side vendor dependency
- unapproved public publication

## Consequences

### Positive
- Chummer gains a visible wow-factor lane that fits the campaign-OS and publication vision.
- The same approved source can now flow into packet, preview, narration, and video siblings.
- Localization leverage becomes much stronger for onboarding, support, and campaign briefing surfaces.

### Negative
- A presenter-video lane can make the product look cheap if it is overused or under-approved.
- Public-facing factual drift becomes more dangerous when the artifact is persuasive and polished.
- Avatar-heavy output can become uncanny or manipulative if identity/consent rules are weak.

## Required follow-through

- add `vidBoard` to `EXTERNAL_TOOLS_PLANE.md`
- add `vidBoard` to `LTD_CAPABILITY_MAP.md`
- add `PUBLIC_VIDEO_BRIEFS.yaml`
- add a video artifact-family section to the structured media canon
- update `JACKPOINT`, `RUNSITE`, and `RUNBOOK PRESS` tool posture
- keep `TABLE PULSE AFTERMATH` video use bounded and later, and do not let presenter video become `TABLE PULSE LIVE` packet authority

## Rule

Chummer may use presenter video to make artifacts feel finished.
It may not let presenter video replace inspectable truth.
