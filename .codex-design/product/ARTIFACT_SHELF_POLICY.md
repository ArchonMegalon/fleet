# Artifact shelf policy

## Purpose

This file defines how personal, campaign, creator, and public artifact shelves stay useful without becoming detached media buckets.

Artifact shelves may help people discover what Chummer made for them.
They may not hide audience posture, locale posture, retention posture, or inspectable source truth.

## Product promise

Every promoted artifact shelf entry must answer four questions visibly:

1. who this artifact is for
2. what language and fallback posture it uses
3. how long the shelf may retain or project it
4. what inspectable source truth it came from

If the shelf cannot answer those four questions honestly, it must fall back to the inspectable packet, receipt, or source-linked text summary instead of pretending the artifact is self-authenticating.

## Truth order

The required truth order for every shelf entry is:

1. inspectable source packet, receipt, or registry truth
2. audience, locale, retention, and publication posture attached to that source truth
3. preview, caption, packet sibling, or shelf metadata projection
4. rendered card, media launch, or artwork

If those layers disagree, the higher layer wins.
Shelf presentation is always subordinate to inspectable source truth.

## Required shelf facets

Every promoted shelf entry must carry or expose:

* artifact identity and family
* current publication or availability posture
* audience class or access class
* locale and fallback posture
* retention posture or expiry window
* inspectable sibling action back to the source packet, receipt, registry record, or source-safe text path

Missing preview art is recoverable.
Missing source truth is not.

## Audience rules

Artifact shelves must show audience posture as first-class meaning, not as optional metadata.

Required audience rules:

* personal shelves default to `me`, claimed-install, or explicitly shared-with-me artifacts
* campaign shelves default to the safest audience variant available for the current workspace surface
* creator shelves distinguish creator-only operating data from public publication posture
* public shelves may expose only artifacts approved for guest or public-account visibility
* device role, platform, or route shape may influence emphasis, but it does not replace audience authority
* if a safer audience variant cannot be proven, the shelf must fail closed to the safer sibling, the inspectable packet, or no launch

Audience labels may not disappear when an artifact is promoted from one shelf to another.

## Locale rules

Artifact shelves must preserve the locale rules already defined by `LOCALIZATION_AND_LANGUAGE_SYSTEM.md`.

Required locale rules:

* preview labels, captions, packet siblings, and launch actions must resolve through one deterministic locale chain
* locale fallback may change presentation language, but it may not change audience, spoiler class, or source identity
* a localized media launch may ship only when the corresponding localized visible copy and inspectable sibling action exist
* when the requested locale is unavailable, the shelf must keep the fallback path visible instead of faking a fully localized artifact
* locale badges, packet revision labels, and source anchors may not be paraphrased into warmer marketing copy

Locale polish is optional.
Locale honesty is not.

## Retention rules

Artifact shelves are projection surfaces, not indefinite archives by default.

Required retention rules:

* retention posture must reuse the owning surface rules from `PRIVACY_AND_RETENTION_BOUNDARIES.md`
* the shelf must distinguish retained-for-return artifacts from short-lived preview or notification artifacts
* a retention badge may summarize policy in plain language, but it must not invent a longer retention promise than the source system allows
* if the artifact or its preview expired, the shelf may retain a bounded tombstone or receipt reference, but it may not pretend the launchable artifact still exists
* public shelves must treat archive or fallback packages as explicitly secondary when current public truth says they are not the primary route

Retention language must explain whether the artifact is current, temporary, expired, or recoverable from source truth.

## Inspectable source truth

Every promoted shelf lane must offer one obvious inspectable sibling path.

Allowed sibling actions include:

* `Open source packet`
* `Inspect receipt`
* `Open campaign source`
* `Open explain packet`
* `Open publication record`
* `Open download truth`

The shelf may be the warm entry point.
It may not be the only route to the underlying truth.

The following claims must always stay inspectable:

* why the artifact exists
* which source packet, receipt, or registry record produced it
* which audience can safely open it
* which locale or fallback path it uses
* whether the artifact is current, expired, revoked, preview-only, or fallback-only

## Shelf families

### Personal shelf

The personal shelf is a return-and-followthrough surface.
It should prioritize the user's current artifacts, bounded history, and next safe action.
It must not leak campaign-private or creator-private artifacts through generic recent-media framing.

### Campaign shelf

The campaign shelf is a workspace projection.
It may show recap cards, primers, mission briefings, evidence rooms, and other publication-safe artifacts only when audience, locale, and source-pack posture stay visible.
Campaign shelf entries may not turn device-role shortcuts into authority over spoiler or GM-only variants.

### Creator shelf

The creator shelf is an operating surface.
It may show compatibility, moderation, ranking, and adoption posture only when those claims remain subordinate to receipt-backed creator truth and the creator-publication policy.
Creator shelf entries may not present discoverability or moderation language as proof of install safety for every table.

### Public shelf

The public shelf is a proof and acquisition surface.
It may help people inspect what Chummer makes, but it must keep recommended download truth, fallback posture, and public-proof posture distinct.
Public shelf entries may not let proof-gallery artifacts masquerade as the primary install route.

## Forbidden modes

Artifact shelves must not:

* auto-play arbitrary media as proof that an artifact is current
* hide source packets or receipts behind media-first chrome
* drop audience labels when an artifact is embedded into another shelf
* let locale fallback erase source anchors or inspectable sibling actions
* imply indefinite retention when the owning surface only allows bounded preview retention
* present rendered cards, clips, or screenshots as stronger truth than the source packet or receipt
* treat the shelf itself as the system of record for campaign continuity, rule truth, moderation evidence, or release authority

## Linked canon

Use this file with:

* `CAMPAIGN_WORKSPACE_AND_DEVICE_ROLES.md`
* `CAMPAIGN_COLD_OPEN_AND_MISSION_BRIEFING_POLICY.md`
* `BUILD_EXPLAIN_ARTIFACT_TRUTH_POLICY.md`
* `CREATOR_PUBLICATION_TRUST_AND_COMPATIBILITY_POLICY.md`
* `PUBLIC_DOWNLOADS_POLICY.md`
* `LOCALIZATION_AND_LANGUAGE_SYSTEM.md`
* `PRIVACY_AND_RETENTION_BOUNDARIES.md`
