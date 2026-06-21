# Table Pulse Opt-Out And Remote Reaction Audit

Date: 2026-05-23
Source zips:

- `/home/tibor/table_pulse_optout_remote_minigame_addendum_20260520.zip`
- `/home/tibor/table_pulse_optout_reaction_minigames_addendum_20260520.zip`

Source prompt: `/home/tibor/CODEX_IMPLEMENTATION_PROMPT_STRICT-6.md`

## Intake Summary

These two new Tibor bundles are not separate programs. They are overlapping addenda on
top of the already-queued Table Pulse heat-reaction work.

Shared new scope:

- GM opt-out and campaign/session pulse policy
- player notification opt-in, opt-out, mute, and quiet-hours posture
- remote reaction mini-games
- GM adjudication packets for remote investigation/interference
- suppression receipts for blocked delivery
- stricter privacy, consent, anti-spam, and rate-limit proof

## Delta Versus Existing Queue

Already covered in `m148`:

- baseline Table Pulse heat thresholds
- baseline push notification and delivery contracts
- EA recipient decision
- GM adjudication lane
- Black Ledger heat projection
- fleet-side privacy/rate-limit and final verdict posture

New delta in these addenda:

- explicit campaign/session opt-out policy defaults
- player-level mute and notification preference receipts
- remote reaction mini-game loop as a bounded interaction model
- suppression receipts for blocked delivery and policy denials
- GM remote-party notice and adjudication specifically for outside investigation/interference

## Product Boundaries

The new addenda reinforce the correct boundary:

- private campaigns default external reactions off
- remote mini-games default off
- player heat notifications default opt-in
- outside reactions never auto-apply
- GM remains final authority

This should be queued as a delta program on top of Table Pulse, not as a rewrite of it.

## Fleet Backlog Mapping

This intake is mapped into a focused `m150` program:

- `next90-m150-design-table-pulse-optout-canon`
- `next90-m150-hub-table-pulse-optout-policies`
- `next90-m150-hub-player-notification-preferences`
- `next90-m150-hub-mobile-remote-reaction-minigames`
- `next90-m150-hub-gm-remote-reaction-adjudication`
- `next90-m150-fleet-table-pulse-suppression-and-privacy-proof`
- `next90-m150-fleet-table-pulse-optout-final-verdict`

That split avoids duplicate queue noise while preserving the new behavioral requirements
from both Tibor addenda.
