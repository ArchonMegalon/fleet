# ADR-0009: External Tools Stay Behind Chummer-Owned Adapters

Date: 2026-03-24

Status: accepted

## Context

- Chummer already has an explicit External Tools Plane for rendering, research, surveys, docs/help, and bounded operator assists.
- The project is integrating more outside capabilities, which raises the risk that a vendor surface becomes de facto product truth.
- The design repo needed a durable decision record that says outside tools are helper planes, not canonical authorities.

## Decision

- External tools always sit behind Chummer-owned adapters.
- External tools may assist, render, notify, archive, visualize, or help operators, but they may not own rules truth, session truth, registry truth, artifact truth, approval truth, or canon truth.
- `chummer6-hub` owns orchestration-side integrations.
- `chummer6-media-factory` owns render and archive integrations.
- `chummer6-design` owns external-tools policy and rollout governance.
- Clients do not integrate directly with third-party tools as product authority.

## Consequences

- Vendor convenience does not justify bypassing Chummer-owned packages, receipts, or approval loops.
- Any provider-assisted output that re-enters Chummer must carry Chummer-side provenance and receipts.
- Future tool additions can now inherit a stable ADR-grade rule instead of starting from scratch.
