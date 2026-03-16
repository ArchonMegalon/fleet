# Design Horizons And LTD Canon Audit

Date: 2026-03-16
Scope: `chummer6-design` future-capability canon, Horizons posture, and external-tools canon drift.

Use this as backlog input for Fleet coordination and queue shaping. The key issue is that active architecture canon is strong, but canonical future-capability design is weak relative to the public guide and the current LTD inventory.

## Hard read

- `chummer6-design` is strong on active architecture and ownership.
- `chummer6-design` is weak on canonical future-capability design.
- The public `Chummer6` guide is currently ahead of canonical design on Horizons storytelling and future capability framing.
- `EXTERNAL_TOOLS_PLANE.md` is stale relative to the live LTD inventory.

## Main design gaps

1. No canonical horizon/capability registry in the `products/chummer` front door.
2. No canonical policy for user-proposed horizon ideas, vote eligibility, or public-signal handling.
3. No canonical guide/horizons relationship policy.
4. No canonical mapping from the real LTD/tool inventory to future capability families.
5. Missing tool canon for:
   - `Soundmadeseen`
   - `Browserly`
   - `Unmixr AI`

## Required design moves

- Add a canonical horizon layer under `products/chummer/`:
  - `HORIZONS.md`
  - `horizons/*.md`
- Add a `PUBLIC_GUIDE_POLICY.md` that defines the guide as downstream-only and prevents it from outrunning canonical horizon docs.
- Add a `HORIZON_SIGNAL_POLICY.md` for advisory user/community participation and signal collection.
- Update `EXTERNAL_TOOLS_PLANE.md` to match the real LTD inventory and explicitly classify missing tools.
- Add a design policy for public guide / horizon media generation and style epochs.
- Decide whether Lua/scripted rulesets are canonical future capability or only guide rhetoric.
- Add non-blocking horizon milestones so future-capability planning becomes visible without blocking foundation closure.
- Add `Chummer6` itself to the design front door as an adjacent public guide lane with an explicit downstream relationship.

## Tool-canon implications

- Promote and explicitly map:
  - `1min.AI`
  - `AI Magicx`
  - `Prompting Systems`
  - `BrowserAct`
  - `Documentation.AI`
  - `ApproveThis`
  - `MetaSurvey`
  - `Teable`
  - `MarkupGo`
  - `PeekShot`
  - `Mootion`
  - `AvoMap`
  - `Internxt`
  - `Paperguide`
  - `Vizologi`
- Add missing canon for:
  - `Soundmadeseen`
  - `Browserly`
  - `Unmixr AI`
- Keep explicit parked/out-of-product posture for:
  - `ChatPlayground AI`
  - `FastestVPN PRO`
  - `OneAir`
  - `Headway`
  - `Invoiless`
  - `ApiX-Drive`

## Working rule for Fleet slices

When a slice touches future capability planning, Horizons, guide generation, or LTD/tool posture:

- prefer canonical design artifacts over guide-only narratives
- treat guide Horizons as downstream explanation, not design truth
- do not integrate a tool just because it is owned
- require explicit promoted / bounded / parked / excluded posture in design canon

## Concrete backlog implications

- Generate a canonical horizon registry in `chummer6-design`.
- Generate a public-guide / horizon sync policy.
- Update external-tools canon to match the actual LTD inventory.
- Add an LTD-to-horizon capability map so Fleet and EA stop improvising tool posture downstream.
