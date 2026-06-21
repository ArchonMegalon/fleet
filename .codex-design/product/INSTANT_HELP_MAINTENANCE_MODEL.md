# Chummer Instant Help Maintenance Model

## Classification

Chummer Instant Help is maintenance infrastructure.

It is not a horizon, campaign feature, marketing surface, or gameplay promise. It belongs to the support, repair, update, and documentation loop.

## Product shape

The user-facing surface is:

```text
Chummer Instant Help
```

The internal subsystem is:

```text
InstantGuidedSupportOrchestrator
```

The normal support loop is:

```text
instant answer
-> optional "Show me" video
-> guided repair
-> automatic check
-> issue report if unresolved
```

No normal Chummer support path should ask the user to book a call.

## Roles

Chummer owns:

* release and installer truth
* build, channel, platform, and update facts
* help facts and repair checklists
* rules-safe explain receipts
* diagnostics, privacy boundaries, and support-case state
* final publication and video freshness decisions

Answerly may:

* turn approved help packets into short support answers
* humanize safe support text
* explain where to click from current Chummer help facts

DocumentationAI may:

* project approved help and documentation sources
* feed searchable public help content

VidBoard may:

* render approved presenter videos for common maintenance tasks
* produce multilingual tutorials from approved source packets
* provide MP4, captions, transcript, poster, and review metadata

Dadan may later:

* collect user-submitted screen recordings for unresolved support cases
* stay opt-in, private, and asynchronous

Lunacal may not appear in the normal Chummer help flow.

## User experience

The first answer should be text.

The video is optional:

```text
Here are the three steps.

[Show me - 42 sec]
[Open setting]
[Run check]
```

The answer should not explain the support architecture. It should name the next action.

## Initial support topics

P0 library:

* install Windows
* install Linux
* first launch
* update Chummer
* restore character
* report a bug
* import Chummer5A
* create first character
* add gear
* privacy and opt out

Black Ledger remains hidden from default support until that surface is ready for broad users.

## Video catalog contract

Each pre-rendered help video needs:

```yaml
id:
topic:
title:
language:
platform:
minimum_build:
maximum_build:
provider: vidboard
provider_asset_id:
mp4_asset_url:
poster_asset_url:
transcript:
captions:
source_document:
source_sha256:
video_sha256:
duration_seconds:
reviewed_by:
status: draft | approved | published | stale | archived
```

## Freshness gate

Create:

```text
INSTANT_SUPPORT_VIDEO_FRESHNESS.generated.json
```

It fails when:

* a referenced UI label changes
* a route changes
* an installer changes
* a workflow changes
* supported platforms change
* the source document hash changes
* the current build exceeds `maximum_build`

## Async video production

New videos are not generated per user.

When the same issue repeats, Chummer creates an anonymized pattern:

```text
support cluster
-> approved source packet
-> script review
-> VidBoard render
-> QA
-> help library
```

Suggested trigger:

```yaml
create_new_video_when:
  same_issue_count_30_days: 5
  or:
    severity: high
  or:
    workflow_is_new: true
```

## Rules boundary

VidBoard and Answerly do not own Shadowrun rules.

For rules-related help:

```text
Chummer computes the result
-> Chummer creates the explain receipt
-> Answerly may humanize the receipt
-> VidBoard may show how to inspect the UI
```

No provider may infer legality, availability, cost, sourcebook interpretation, or character mechanics.

## Feature flags

```yaml
instant_support_enabled: true
instant_support_video_library_enabled: true
vidboard_operator_render_enabled: false_until_verified
vidboard_api_render_enabled: false
lunacal_chummer_support_enabled: false
dadan_async_issue_recording_enabled: false_until_verified
```

## Required maintenance components

```text
InstantGuidedSupportOrchestrator
InstantSupportIntentRouter
InstantSupportVideoCatalog
InstantSupportDiagnosticRunner
SupportVideoFreshnessService
SupportEscalationService
VidBoardSupportVideoAdapter
```

## Proof artifacts

```text
fleet/_completion/instant_support/
  INSTANT_SUPPORT_ARCHITECTURE.generated.json
  INSTANT_SUPPORT_INTENT_ROUTER.generated.json
  INSTANT_SUPPORT_DIAGNOSTIC_E2E.generated.json
  INSTANT_SUPPORT_VIDEO_FRESHNESS.generated.json
  INSTANT_SUPPORT_PRIVACY_BOUNDARY.generated.json
  INSTANT_SUPPORT_RULESAFE_BOUNDARY.generated.json
  INSTANT_SUPPORT_ESCALATION_E2E.generated.json
  FINAL_INSTANT_GUIDED_SUPPORT_VERDICT.md

fleet/_completion/vidboard/
  VIDBOARD_PROVIDER_VERIFICATION.generated.json
  VIDBOARD_COMMERCIAL_USE_AND_WATERMARK_PROOF.generated.json
  VIDBOARD_AVATAR_AND_VOICE_CONSENT.generated.json
  VIDBOARD_FIRST_CHUMMER_TUTORIAL.generated.json
  VIDBOARD_MULTILINGUAL_TUTORIAL_PROOF.generated.json
  VIDBOARD_VIDEO_EXPORT_PROOF.generated.json
  VIDBOARD_HUMAN_REVIEW.md
  FINAL_VIDBOARD_SUPPORT_VIDEO_VERDICT.md
```

## Exit bar

Chummer Instant Help is ready only when a user can:

1. ask for help without knowing internal product names
2. get a short answer
3. watch a current optional video
4. run a repair or check
5. create a private support packet if unresolved

The design succeeds when the user never needs to understand which provider helped.
