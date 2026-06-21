# Runsite host mode policy

## Purpose

Runsite host mode is a premium orientation layer for a published location pack.
It helps players or GMs understand a space before the run starts without turning narration, clips, or audio into tactical authority.

## Product promise

Approved runsite packs may launch a short host-led clip, optional audio, route overlay, and optional explorable tour as one bounded orientation bundle.
The bundle exists to frame the venue and the likely movement logic before live play, not to replace inspectable route, map, tour, or pack truth once decisions matter.

## Truth order

Runsite host mode stays subordinate to this truth order:

1. approved runsite pack
2. approved route summary and route overlay
3. inspectable tour or map sibling
4. rendered host clip or optional narration

If the host clip, audio layer, route overlay, and tour disagree, the inspectable route or tour sibling wins.
The clip is a summary surface, not a rules, route, or tactical control surface.

## Inspectable route and tour truth

Every promoted host-mode launch must preserve:

* an `Open route overlay` action
* an `Open explorable tour` action when a tour exists
* an `Inspect runsite pack` action that exposes the underlying approved pack and route summary references

Route, map, and tour siblings must stay visible before playback starts and remain reachable while playback is active.
The host clip may summarize key approach pressure, hotspots, and access posture, but it may not become the only inspectable path to those facts.

## Host-mode limits

Host mode is preview-safe orientation only.

Forbidden:

* live combat or surveillance authority
* hidden tactical claims that do not exist in the approved runsite pack or route summary
* branching instructions that outrank route or tour truth
* replacing route, map, or tour siblings with a single autoplay clip
* implying that the clip reflects live state after publication without a refreshed first-party route or pack receipt

Media never becomes tactical authority.

## Receipt and approval minimums

Every published runsite host artifact must preserve:

* `runsite_pack_id`
* `route_summary_id`
* `inspectable_route_ref`
* `inspectable_pack_ref`
* `tour_ref` when a tour sibling exists
* `publication_ref`
* `locale`
* `audience`

Approval scope must bind the exact pack revision, route summary revision, locale, and audience posture that the clip summarizes.

## Launch and UI rules

Runsite host mode may launch from campaign, mobile, or artifact-gallery surfaces before live play.
The default choice must keep route-first and tour-first siblings visible as equal first-party actions rather than hiding them behind warmer host copy.
If verification, approval, or sibling routing is missing, the product must fail closed to the route overlay, explorable tour, or inspectable pack page.

## Non-goals

This policy does not define live encounter tooling, fog-of-war state, dynamic enemy truth, or tabletop automation.
Those remain outside runsite host mode.
