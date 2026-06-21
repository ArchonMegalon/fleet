# vidBoard and LTD wow-factor workflows

## Purpose

This file turns the current owned LTD stack into concrete Chummer product experiences instead of a loose tool inventory.

It is deliberately biased toward:
- visible wow-factor
- multilingual reach
- campaign-OS fit
- bounded truth discipline
- workflow realism with the current repo split

## Audit summary

Project Chummer already has most of the raw ingredients for striking media and companion experiences.

What is already owned and relevant:
- `vidBoard` for structured presenter video, multilingual voice, custom avatars, and document/URL/text-to-video
- `Soundmadeseen` for narration-rich companion media
- `MarkupGo` for packet and document rendering
- `PeekShot` for preview/share cards
- `First Book ai` for long-form blueprint and script scaffolding
- `Documentation.AI` for downstream guide/help projection
- `Mootion` for bounded short motion support
- `AvoMap` and `Crezlo Tours` for route and explorable location lanes
- `hedy.ai`, `Nonverbia`, and `Unmixr AI` for bounded post-session structure, coaching, and voice experimentation
- `ApproveThis`, `MetaSurvey`, and `BrowserAct` for approval, usefulness capture, and vendor-automation fallback

What is still missing in canon:
- one normalized machine-readable recipe registry that names primary lane, fallback lane, approval path, receipt owner, and publication surfaces together
- one stronger public proof shelf that makes the artifact factory visible as product truth instead of horizon prose alone
- one clearer promotion plan for which owned LTD lanes should move from tracked posture into real runtime adapters first

## Maintenance workflow - Chummer Instant Help video library

This is not a horizon.

VidBoard's Chummer support role is maintenance video production: pre-rendered, reviewed clips that explain common tasks and repairs from approved Chummer help packets.

The user flow is:

1. Chummer Instant Help gives a short text answer.
2. The user may choose `Show me`.
3. Chummer selects a current video from the support catalog.
4. The user can run the matching repair or check.
5. If unresolved, Chummer creates a private support packet.

VidBoard should not be treated as an instant runtime video API.
Until provider API proof exists, video creation is operator-driven and asynchronous.

Initial maintenance topics:

* install Windows
* install Linux
* update Chummer
* restore character
* report a bug
* import Chummer5A
* create first character
* add gear
* privacy and opt out

Freshness is mandatory.
A help video becomes stale when the referenced build, installer, UI label, route, workflow, or source document changes.

## Workflow 1 - Pocket Johnson mission briefing

### User story
A GM prepares a run. Before the session, every player gets a short, polished mission briefing in their chosen language on mobile or desktop.

### Why it is wow
It feels like the campaign arrived prepared.
It turns dossiers and packets into a moment.
It is instantly legible to players who would never read a long PDF first.

### Pipeline
1. GM approves a `mission_brief_packet` in Hub.
2. Hub builds a short source-truth script from the approved packet.
3. `vidBoard` renders a 45-90 second avatar-led `mission_brief_video` in the target locale.
4. `MarkupGo` renders the sibling mission packet.
5. `PeekShot` renders a preview/share card.
6. Registry stores the published refs.
7. The mobile app and claimed desktop installs show a "Watch briefing" card for the campaign.

### LTD stack
- `vidBoard` - primary presenter-video lane
- `MarkupGo` - packet sibling
- `PeekShot` - preview card
- `First Book ai` - optional script blueprint helper
- `ApproveThis` - approval checkpoint
- `BrowserAct` - fallback publication/upload automation

### Guardrails
- no improvisational facts beyond the approved packet
- public/campaign-visible output only after approval
- no fake quotes from player characters unless explicitly authored

## Workflow 2 - Join-the-campaign primer video

### User story
A new player joins a campaign and gets a clean primer video plus a grounded primer packet in the right language.

### Why it is wow
This removes the "read these six PDFs" onboarding tax.
It makes Chummer feel like a real campaign home instead of a character file utility.

### Pipeline
1. Campaign has a canonical `campaign_primer_pack`.
2. Hub assembles an approved short script and longer packet.
3. `vidBoard` renders `campaign_primer_video`.
4. `MarkupGo` renders the primer packet.
5. `Documentation.AI` projects the same approved content into help/guide posture if needed.
6. The first claimed install or campaign join flow offers "Watch primer" and "Open full primer" side by side.

### LTD stack
- `vidBoard`
- `MarkupGo`
- `Documentation.AI`
- `First Book ai`
- `PeekShot`

### Best surface
- Hub home
- claimed install continuation flow
- mobile campaign home

## Workflow 3 - Runsite host clip

### User story
Before the team enters a location, the GM can open a short host-led orientation clip that frames the venue, route pressure, and key hotspots.

### Why it is wow
A map becomes a story beat instead of a static sheet.
The runsite feels alive before any tokens move.

### Pipeline
1. GM publishes a `runsite_pack`.
2. `Crezlo Tours` or `AvoMap` owns the spatial artifact.
3. Hub creates a concise orientation script from approved pack metadata.
4. `vidBoard` renders a 30-60 second `runsite_orientation_video`.
5. `PeekShot` generates the thumbnail/preview.
6. Optional `Soundmadeseen` audio-only version exists for lower-friction mobile playback.

### LTD stack
- `Crezlo Tours`
- `AvoMap`
- `vidBoard`
- `PeekShot`
- `Soundmadeseen`
- `Mootion` for bounded motion-only overlays if needed

### Guardrails
- not a tactical live-combat system
- not real-time surveillance or auto-GMing
- route overlays remain inspectable outside the clip
- route overlays and explorable tours remain first-party truth during the clip
- host narration may not become the only authority for access, pressure, or hotspot claims

## Workflow 4 - Fix landed / what changed video

### User story
A user reports a bug. When the fix reaches their release channel, Chummer sends a short localized explanation of what changed and what to do next.

### Why it is wow
Support stops feeling like a dead-end inbox.
Closure becomes visible and personal.

### Pipeline
1. Support case closes in Hub.
2. Registry confirms the fix actually reached the reporter's channel.
3. Hub generates an approved short `support_closure_script`.
4. `vidBoard` renders a `support_closure_video` in the user's locale.
5. `Documentation.AI` and help surfaces receive the sibling written explanation.
6. `Emailit` can deliver the message and deep-link back to Hub/help/downloads.
7. `MetaSurvey` optionally asks "did this solve it?" after update.

### LTD stack
- `vidBoard`
- `Documentation.AI`
- `Emailit`
- `MetaSurvey`
- `ApproveThis`

### Guardrails
- only send "fixed" when the fix has really landed on the user's channel
- keep the video short and practical
- the canonical truth remains the support case and release metadata, not the video

## Workflow 5 - Release shelf explainer bundle

### User story
Every important preview release ships with a human-friendly 60-second explainer, a written notes page, and a share card.

### Why it is wow
The preview shelf looks deliberate instead of improvised.
The product appears alive and cared for.

### Pipeline
1. Release notes and approved highlights exist.
2. `vidBoard` renders a `release_explainer_video`.
3. `PeekShot` renders a social/share card.
4. `Documentation.AI` or Hub guide surfaces render the written version.
5. The release shelf surfaces the video beside the installer and notes.

### LTD stack
- `vidBoard`
- `PeekShot`
- `Documentation.AI`
- `BrowserAct` when publishing or download-shelf automation needs a fallback

## Workflow 6 - Player-safe story-so-far recap

### User story
After a consented session, the group can get a short neutral story-so-far recap for the next session.

### Why it is wow
The table gets memory continuity without somebody volunteering to write a long summary.

### Pipeline
1. `hedy.ai` produces the structural digest.
2. `Nonverbia` optionally produces coaching signals for the GM-only lane.
3. Hub creates an approved player-safe recap script from the neutral digest.
4. `vidBoard` renders a `player_safe_recap_video` or `Soundmadeseen` renders an audio recap when video is unnecessary.
5. `MarkupGo` renders the written recap sibling.
6. `PeekShot` provides the preview card.

### LTD stack
- `hedy.ai`
- `Nonverbia`
- `vidBoard`
- `Soundmadeseen`
- `MarkupGo`
- `PeekShot`
- optional `Unmixr AI` for bounded dubbing/voice experiments

### Hard boundaries
- no live monitoring
- no player ranking
- no blame language
- no moderation or discipline output
- no publication without review

## Workflow 7 - GM-private debrief walkthrough

### User story
After a session, the GM can receive a private coaching walkthrough that highlights likely pacing drags, unresolved hooks, and next-session questions.

### Why it is wow
It feels like a real companion system instead of a static log dump.

### Pipeline
1. Post-session consent and retention rules are checked.
2. `hedy.ai` creates structure and highlight digest.
3. `Nonverbia` creates the coaching layer.
4. Hub assembles a private debrief script.
5. `vidBoard` or `Soundmadeseen` renders a private `gm_private_debrief_video`.
6. `MarkupGo` renders the debrief packet.

### Why this is later
This is powerful but much more privacy-sensitive than public explainers or primers.
Ship it after the safer wow lanes.

## Workflow 8 - Creator promo kit

### User story
When a creator publishes a pack, primer, runsite, or dossier bundle, Chummer can generate a promo kit automatically.

### Why it is wow
Creator output becomes presentable and discoverable without extra manual media work.

### Pipeline
1. Creator publishes an approved artifact.
2. Registry confirms the publication manifest.
3. Hub assembles a short promo script.
4. `vidBoard` renders a `creator_promo_video`.
5. `PeekShot` renders share cards.
6. `MarkupGo` renders the long-form companion packet when relevant.
7. Optional `Mootion` or `AvoMap` clips can provide movement or route context.

### LTD stack
- `vidBoard`
- `PeekShot`
- `MarkupGo`
- `Mootion`
- `AvoMap`
- `Documentation.AI`

## Workflow 9 - Mobile home feels alive

### User story
The mobile app home is not just a list. It greets the user with the right short artifact for the current moment.

### Candidate cards
- "Watch mission briefing"
- "Watch campaign primer"
- "See what changed since last session"
- "Issue fixed on your device"
- "Open player-safe recap"
- "Walk the runsite"

### Principle
The wow-factor should come from the right artifact showing up at the right moment, not from auto-playing random media.

## Best immediate shipping order

### First
- release explainer videos
- campaign primer videos
- mission briefing videos

### Next
- runsite host clips
- creator promo kits
- support closure videos

### Later
- player-safe recap videos
- GM-private debrief walkthroughs

## Concrete file changes this implies

Add or update:
- `STRUCTURED_VIDEO_AND_NARRATED_MEDIA_MODEL.md`
- `PUBLIC_VIDEO_BRIEFS.yaml`
- `EXTERNAL_TOOLS_PLANE.md` to include `vidBoard`
- `LTD_CAPABILITY_MAP.md` to classify `vidBoard`
- `horizons/jackpoint.md`
- `horizons/runsite.md`
- `horizons/runbook-press.md`
- optionally `horizons/table-pulse.md` with a bounded player-safe recap-video note
- `PUBLIC_FEATURE_REGISTRY.yaml` for video-shaped artifact previews and release/help explainers

## Most important design rule

Do not use video everywhere.

Use it where it:
- reduces friction fast
- increases comprehension
- helps localization materially
- makes the product feel premium
- still keeps inspectable Chummer truth beside it
