# Living World Engagement Audit

Date: 2026-05-23
Source bundle: `/home/tibor/chummer_living_world_engagement_loops_design_20260520.zip`
Source prompt: `/home/tibor/CODEX_IMPLEMENTATION_PROMPT_STRICT-5.md`

## Intake Summary

This newer Tibor bundle is not a replacement for the Table Pulse heat reaction package.
It is a broader program that uses Table Pulse as one input lane inside a wider living
world engagement system.

The bundle adds concrete product scope for:

- notification inbox and mute/settings surfaces
- faction standing orders
- rumor market and public-safe intel hooks
- runner passport and reputation history
- downtime micro-actions
- rival team / world response hooks
- newsreel and digest delivery
- BeHuman engagement rails
- Answerly support explanation rails

## Delta Versus The Already-Queued Table Pulse Program

Already queued under `m148`:

- heat reactions
- push subscriptions
- EA recipient decisions
- GM adjudication
- privacy and rate-limit gates
- Black Ledger heat projection
- final heat-reaction verdict

New delta in this bundle:

- durable notification inbox and packet history
- faction standing order contribution loop
- rumor market with confidence labels and redaction posture
- runner passport history without shame rankings
- downtime actions as GM prompts/receipts rather than auto-rules mutation
- broader living-world delivery receipts across PWA/in-app/email
- bounded BeHuman and Answerly engagement roles

## Current Repo Reality

The repo does not yet show this broader engagement loop as a landed system.

Observed practical gap:

- the hub/mobile surface does not yet show the wider inbox/orders/passport/downtime
  routes named in the new bundle as a single governed feature family
- the current service worker foundation is still cache-first and not yet the richer
  interaction rail this broader loop expects

## Product Boundaries

The new bundle is correct to require:

- GM final authority
- private campaign data remains private
- no external action auto-applies to the table
- consent, quiet hours, mutes, and rate limits
- no shame/toxic ranking patterns
- all actions emit Chummer-owned receipts

Important claim boundary:

This is a living-world engagement layer, not an autonomous world-simulation permission
slip. The system should feel alive, but the table remains governed.

## Fleet Backlog Mapping

This bundle has been mapped into a new `m149` program:

- `next90-m149-design-living-world-engagement-canon`
- `next90-m149-hub-notification-inbox-and-settings`
- `next90-m149-hub-faction-standing-orders`
- `next90-m149-hub-rumor-market`
- `next90-m149-hub-runner-passport`
- `next90-m149-hub-downtime-micro-actions`
- `next90-m149-hub-mobile-living-world-delivery-receipts`
- `next90-m149-hub-behuman-answerly-engagement-bounds`
- `next90-m149-fleet-living-world-final-verdict`

The intent is to keep `m148` focused on heat-reaction truth while `m149` owns the wider
engagement loops that build on top of it.
