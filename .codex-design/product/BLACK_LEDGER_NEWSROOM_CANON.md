# Black Ledger Newsroom Canon

## Mission

Black Ledger Newsroom turns public-safe Chummer receipts into believable in-world video bulletins.

It should feel like a real broadcast from the Chummer world, not a website animation.

## Core identity

```yaml
name: Black Ledger Newsroom
tagline: The city reports back.
format: short-form cyberpunk news bulletin
primary_audience:
  - players
  - GMs
  - community watchers
  - faction members
  - curious visitors
```

## Tone

```yaml
tone:
  - sharp
  - credible
  - slightly strange
  - restrained humor
  - tactical
  - not goofy
  - not generic AI hype
```

## Broadcast categories

```yaml
turn_newsreel:
  duration: 45-90 seconds
  use: world tick summary

breaking_breach:
  duration: 20-45 seconds
  use: high heat / Table Pulse / Black Ledger breach

faction_bulletin:
  duration: 20-40 seconds
  use: faction-specific public-safe update

karma_forge_report:
  duration: 30-60 seconds
  use: package/rule idea status

event_invite:
  duration: 15-30 seconds
  use: BeHuman / ChummerCon / workshop promo

weekly_city_pulse:
  duration: 60-120 seconds
  use: longer roundup
```

## Truth model

Every news video must identify the source of its story:

```yaml
truth_sources:
  - BlackLedgerTickReceipt
  - HeatThresholdReceipt
  - FactionScoreDeltaReceipt
  - KarmaForgePackageReceipt
  - EventCloseoutReceipt
  - Support/ReleaseReceipt
```

## Dramatization model

Visual footage can be:
- actual first-party UI capture;
- generated reconstruction;
- public-safe symbolic B-roll;
- fictional studio graphics.

Every generated reconstruction must be marked internally:

```yaml
visual_truth:
  - literal_capture
  - public_safe_reconstruction
  - illustrative_broll
  - editorial_graphic
```

Public copy may say:

```text
Some footage is reconstructed from public-safe receipts.
```

## Hard boundaries

Never include:
- private campaign details;
- runner names without consent;
- GM secrets;
- sourcebook text;
- real person likenesses;
- real public figure likenesses;
- provider branding;
- unproven product claims.

## Flagship requirement

A flagship newsroom bulletin must include:
- a host;
- B-roll;
- lower thirds;
- captions;
- audio;
- visual QA;
- public-safety receipts;
- source receipt links;
- human creative review.
