# Product Spine Redesign

This document is the canonical redesign layer above the detailed Chummer product specs.
It exists to prevent the product from drifting into many individually certified slices that do not obviously serve the same user loop.

## Design Thesis

Chummer6 is an explainable campaign OS.
The product should be judged by whether it helps a table build correctly, run reliably, remember consequences, explain truth, and publish projections safely.

The flagship promise is not that every provider, route, video, or future Horizon exists.
The flagship promise is that the core campaign loop remains understandable under pressure.

## The Spine

1. **Build correctly**
   A runner can create, inspect, validate, save, reopen, and explain a character under every supported ruleset and build method.

2. **Run reliably**
   A table can start, reconnect, recover, and continue without hidden state drift.

3. **Remember the campaign**
   Sessions produce durable consequences, recaps, faction state, locations, and job seeds without inventing facts.

4. **Explain everything**
   Mechanics, character deltas, generated artifacts, release claims, and public routes point back to owned truth.

5. **Publish projections**
   Dossiers, videos, runbooks, public pages, and newsroom output are approved projections of Chummer truth.

## Product Surfaces

The primary surfaces are:

- **Runner Workbench**: dense desktop build and character operation.
- **GM Cockpit**: preparation, live operation, recovery, and closeout.
- **Campaign Memory**: dossiers, recaps, history, provenance, and share-safe views.
- **Living City**: Black Ledger map, factions, newsroom, open jobs, and world ticks.
- **Publishing Studio**: dossiers, runbooks, videos, public pages, and approval workflows.
- **Admin / Proof**: live release truth, journey gates, provider receipts, and gold graph.

The desktop client should remain Chummer5A-familiar: compact, visible, label-rich, scroll-safe, and built for repeated use.
Public and Black Ledger surfaces may be cinematic, but only when backed by Chummer-owned receipts.

## Horizons Are Capability Lanes

Horizons are not separate products.
They are future capability lanes attached to the spine:

- NEXUS-PAN: run reliably.
- ALICE: build correctly and explain everything.
- KARMA FORGE: governed rule evolution.
- JACKPOINT: campaign memory and projection.
- RUNSITE: mission-space operation.
- RUNBOOK PRESS: campaign export.
- TABLE PULSE: live pressure and aftermath.
- BLACK LEDGER: living city projection.
- COMMUNITY HUB: table discovery, preflight, and closeout.

## Providers Are Adapters

Rafter, Pixefy, MagicFit, and similar tools are adapters.
They may verify, render, inspect, or project.
They must not own rules truth, campaign truth, release truth, privacy truth, publishing authority, or gold readiness.

Provider receipts are necessary proof inputs.
They are not human-quality flagship claims by themselves.

## Gold Graph

The gold graph is the current whole-product proof layer.
It references the spine, journey gates, release truth, live status, provider receipts, and human review artifacts.

Older closure folders may remain as history.
Only the current gold graph should claim whole-product readiness.

## Migration Plan

1. Anchor all new work to `PRODUCT_SPINE.yaml`.
2. Require every Horizon, provider gate, public route, and generated artifact to name its spine loop.
3. Collapse future whole-product verdicts into `FINAL_GOLD_GRAPH.generated.json`.
4. Prefer simulated user journeys over receipt-only gates.
5. Promote media only through prompt approval, provider receipt, human review, and Chummer-owned publication.
6. Keep dense desktop usability release-blocking for flagship claims.

## Acceptance Bar

The redesign is working when a release reviewer can answer five questions without reading a dozen closure folders:

- Can a user build correctly?
- Can a table run reliably?
- Does the campaign remember consequences?
- Can the product explain every claim?
- Are published artifacts only approved projections?
