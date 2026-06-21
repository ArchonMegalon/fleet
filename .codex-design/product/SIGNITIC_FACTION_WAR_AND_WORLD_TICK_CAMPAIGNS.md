# Signitic Faction War and World Tick Campaigns

## Purpose

This file defines how Chummer may use Signitic campaigns for BLACK LEDGER, Community Hub, creator, and release outreach.

Signitic is a strong fit for BLACK LEDGER only as a passive propaganda and outreach rail. It may project approved messages through managed email signatures, but it must never own world truth, campaign truth, notification truth, support truth, analytics interpretation, or individual authorization.

The product rule is:

> BLACK LEDGER creates the city event. Hub publishes the truth. Media Factory makes it inspectable and beautiful. Signitic lets managed email carry the rumor.

## Capability fit

The approved capability assumption is limited to email-signature and banner-campaign features:

- centralized managed signatures
- targeted banner campaigns by team, group, role, or domain
- campaign priority and rotation
- A/B banner or message testing
- click and engagement reporting
- UTM-ready links into first-party analytics

Those capabilities are useful because BLACK LEDGER needs visible, low-friction world texture. They are not enough to make Signitic an event, notification, or canon system.

Any banner art, ticker card, or landing media amplified by this lane must meet the flagship media bar: polished poster quality, vivid color, and diegetic augmented-reality overlays that help a runner understand the event. Signitic projects approved assets; Media Factory and Hub own the production standard and page truth.

## Core boundary

Signitic may project approved BLACK LEDGER, Community Hub, release, creator, and public-trust CTAs through managed email signatures.

Signitic must not own:

- campaign truth
- world truth
- private player or runner state
- faction-secret state
- support-case status
- account, security, or entitlement notices
- analytics interpretation or product decisions
- individual notification delivery guarantees
- authorization checks

Every Signitic CTA must land on a first-party Chummer destination. Hub owns the destination, the permissions check, and the receipt trail.

## Managed-account scope

Use Signitic only for managed Chummer/Fleet/Hub/Community Hub/operator accounts.

Allowed sender groups:

- core team
- hub support
- fleet ops
- media factory
- creator success
- GM pilot operators
- BLACK LEDGER organizers
- faction-seat coordinators
- Community Hub operators

Do not target normal player inboxes or infer private player state from signature campaigns. Segments are role and cohort level only.

## Primary workflows

### World tick campaign

After an approved world tick, Fleet or Hub may create a `WorldTickSignatureCampaign` packet.

The packet projects one or more public-safe CTAs such as:

- open the city ticker
- view the mission market
- watch a newsreel
- report intel
- read a faction statement

Signitic rotates the approved banner variants. Hub remains the owner of the tick page, visibility grade, and conversion events.

### Faction propaganda rotation

For a faction conflict, each managed segment may receive a different approved faction voice for the same underlying event.

Examples:

- Renraku frames the Tacoma event as contained security work.
- Horizon frames it as public transparency after corporate violence.
- Aztechnology frames the Puyallup response as humanitarian relief.

The competing narratives are allowed to differ in voice and framing. They must link back to Chummer-owned pages where visibility rules, evidence paths, and public-safe claims are enforced.

### GM job recruitment

When the Mission Market has open jobs, Signitic may amplify GM or player recruitment through managed organizer, creator, or support accounts.

Allowed CTAs:

- open the Community Hub board
- adopt a GM job
- review open runs
- schedule a GM clinic

The OpenRun, roster, table contract, and scheduling receipts remain Hub-owned.

### Intel drive

Signitic may invite public or managed cohorts to contribute table lore or city intel.

Allowed path:

`Signitic CTA -> chummer.run/intel/report -> FacePop or Hub explainer -> Deftform intake -> Hub review queue`

Reviewed intel may become map pressure, job seeds, or news candidates only after Chummer-owned review. Raw submissions are not canon.

### Faction-seat turn reminder

For managed faction-seat or organizer accounts, Signitic may carry passive reminders for governed faction-turn windows.

Allowed path:

`Signitic CTA -> Hub faction console -> NextStep checklist -> Hub turn receipt`

NextStep may execute the operator checklist. Hub owns faction-turn truth and closeout receipts.

### Seasonal honors and newsreel distribution

After a season update or approved newsreel package, Signitic may amplify:

- runner legends
- GM honors
- faction momentum
- intel contributor spotlights
- city recap clips
- creator/open-run pushes

Seasonal honors must remain typed, source-backed, and public-safe. A high-click banner cannot promote a raw leaderboard into truth.

## Packet contract

```yaml
world_tick_signature_campaign:
  key: seattle_tick_007
  source_truth: Chummer.World.Contracts.WorldTick
  owner_repo: chummer6-hub
  campaign_type: world_tick
  signitic_role: projection_only
  approval_required: true
  source_receipts:
    - world_tick_receipt_id
    - publication_visibility_receipt_id
  audience_segments:
    - gm_pilot
    - black_ledger_organizers
    - creator_success
  variants:
    - id: job_market
      banner: "Seattle Tick 07: 3 new jobs are live."
      cta: "Open Mission Market"
      destination: "https://chummer.run/world/seattle/jobs"
      utm_campaign: seattle_tick_007
      utm_content: job_market
    - id: city_ticker
      banner: "Tacoma heat rose. Renraku denies everything."
      cta: "Read City Ticker"
      destination: "https://chummer.run/world/seattle/ticks/007"
      utm_campaign: seattle_tick_007
      utm_content: city_ticker
  forbidden:
    - private_campaign_state
    - faction_secret_state
    - personal_support_status
    - runner_specific_consequence
    - account_or_security_notice
```

## Segment registry

```yaml
signitic_segments:
  core_team:
    purpose: release, public launch, and public proof CTAs
  hub_support:
    purpose: help, downloads, known fixes, and support closure projection
  fleet_ops:
    purpose: governance, pulse, operator, and release-control links
  media_factory:
    purpose: artifact, newsreel, preview-card, and public proof links
  creator_success:
    purpose: creator programs, runbooks, and mission-pack calls
  gm_pilot:
    purpose: open runs, scheduling, GM clinics, and starter jobs
  black_ledger_organizers:
    purpose: world ticks, map review, intel review, and publication approval
  faction_seat_coordinators:
    purpose: faction turns, operation closeout, and public statement review
  community_hub:
    purpose: open-run recruitment, table adoption, and season updates
```

Segments must not encode private player effects, faction secrets, or support-case state.

## Metrics and interpretation

Signitic metrics are campaign telemetry, not product truth.

Track these in Hub or Fleet after UTM landing:

```yaml
signature_campaign_metrics:
  clickthrough_rate:
    by_campaign: true
    by_variant: true
    by_segment: true
  destination_conversion:
    - open_run_view
    - gm_job_adoption
    - intel_report_started
    - intel_report_submitted
    - newsreel_view
    - faction_newsletter_view
    - productlift_vote
  support_side_effects:
    - confused_support_contacts
    - misrouted_bug_reports
  world_effect:
    - jobs_adopted_after_campaign
    - intel_submitted_after_campaign
    - session_scheduled_after_campaign
```

Product Governor review must consider side effects. A high-click banner that creates support confusion, spoiler leakage, or false expectation is a failure.

## Approval and rollback

Every Signitic BLACK LEDGER campaign requires:

- approved source truth
- approved public-safe or segment-safe claim text
- first-party destination URL
- UTM campaign naming
- owner repo
- rollback owner
- expiry or review date
- kill switch path

Campaigns must be retired or superseded when the underlying world tick, open run, faction state, or public claim is withdrawn.

## Non-goals

Signitic is not:

- a newsletter sender
- a campaign engine
- a notification service
- a support update channel
- a player personalization engine
- a faction-secret delivery system
- an analytics source of truth

For newsletters, Hub or a separate broadcast layer owns delivery. Signitic may only amplify a newsletter by linking to a first-party brief.
