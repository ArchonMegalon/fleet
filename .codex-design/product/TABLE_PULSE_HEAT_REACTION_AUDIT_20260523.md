# Table Pulse Heat Reaction Audit

Date: 2026-05-23
Source bundle: `/home/tibor/table_pulse_heat_reaction_pwa_design_20260520.zip`
Source prompt: `/home/tibor/CODEX_IMPLEMENTATION_PROMPT_STRICT-4.md`

## Intake Summary

The Tibor bundle is concrete and backlog-worthy. It defines a bounded Table Pulse / heat
reaction system for live GM sessions with:

- session heat domains and threshold events
- PWA push and in-app notification delivery
- EA-assisted recipient selection
- player and faction reaction packets
- GM adjudication as the final authority
- Black Ledger public-safe projection only after consent and GM-safe redaction

The strict implementation prompt and the bundled acceptance gates are aligned. The
design is not just speculative product prose; it names routes, API contracts, receipts,
privacy gates, and verification expectations.

## Current Repo Reality

The design is not landed yet.

Observed repo gaps:

- `chummer6-hub/Chummer.Run.Api/wwwroot/service-worker.js` and
  `chummer6-hub/Chummer.Run.Api/wwwroot/service-worker.js` currently implement
  install/activate/fetch caching only.
- No `push`, `notificationclick`, or `notificationclose` service-worker handlers are
  present on the public PWA rail.
- No current API route hits were found for:
  - `/api/v1/account/push-subscriptions`
  - `/api/v1/account/notifications/settings`
  - `/api/v1/campaigns/{campaignId}/sessions/{sessionId}/pulse/settings`
  - `/api/v1/account/notifications/{packetId}/react`
  - `/api/v1/campaigns/{campaignId}/sessions/{sessionId}/pulse/reactions/{reactionId}/adjudicate`
- Heat concepts already exist in the broader campaign/query space, but the live-session
  Table Pulse loop described in the Tibor bundle is not yet wired as a governed
  end-to-end system.

## Acceptance Bar

The bundle’s acceptance gates are the right bar:

- GM can configure session pulse settings
- threshold events fire by domain
- external reactions are off by default for private campaigns
- EA recipient decision emits a receipt
- PWA push subscription works
- push and click handlers work in the service worker
- notifications are public-safe and redacted
- reactions never apply without GM adjudication
- consent, quiet hours, and rate limits pass
- every action emits Chummer-owned receipts

The design must stay fail-closed on:

- private GM data leakage
- push without consent
- outside reactions auto-applying to a live table
- Black Ledger projection without a public-safe receipt

## Fleet Backlog Mapping

The Tibor bundle has been mapped into concrete fleet packages:

- `next90-m148-design-table-pulse-canon`
- `next90-m148-hub-session-heat-thresholds`
- `next90-m148-hub-pwa-heat-notification-contracts`
- `next90-m148-mobile-pwa-heat-reaction-surface`
- `next90-m148-ea-table-pulse-recipient-decision`
- `next90-m148-hub-gm-heat-reaction-adjudication`
- `next90-m148-fleet-table-pulse-privacy-and-rate-limit-gates`
- `next90-m148-hub-black-ledger-heat-projection`
- `next90-m148-fleet-table-pulse-final-verdict`

This split is intentionally more scheduler-friendly than the raw bundle:

- hub/mobile shared work is split into repo-owned packages
- fleet owns gates and final verdict proof
- design owns canon and bounded claims
- executive-assistant owns recipient suggestion logic

## Design Decision

This should enter the fleet as a flagship-adjacent product program, but not be marketed
as autonomous world reaction until the privacy, consent, receipt, and GM-authority gates
prove out.

The Tibor bundle’s own caution is correct:

- Table Pulse can be a strong flagship surface
- but it must launch as GM-governed, consented, public-safe escalation
- not as uncontrolled external interference with live sessions
