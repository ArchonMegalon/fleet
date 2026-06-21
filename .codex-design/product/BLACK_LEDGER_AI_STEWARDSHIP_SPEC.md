# Black Ledger AI Stewardship Spec

## Purpose

Black Ledger may use AI interim stewards to keep the preview world moving before verified human stewards take over. AI never outranks human authority and never becomes release truth by itself.

## Authority order

```yaml
authority_order:
  - verified_human_steward
  - verified_operator
  - product_governor
  - ai_interim_steward
  - deterministic_seed_fallback
```

## Interim AI roles

Global roles:

- Ledger GM
- Public Intel Provider
- Package Pressure Analyst
- Privacy Marshal
- Closeout Clerk

Faction roles:

- Faction Leader
- Field GM
- Intel Provider

## What AI may do

- propose a world tick
- summarize public-safe faction pressure
- update seeded preview package pressure
- draft closeout motion
- redact private details before public rendering

## What AI may not do

- publish private campaign, support, or account data
- copy sourcebook text
- mutate world state without a receipt
- overrule verified human stewardship
- claim release truth, roadmap truth, or package promotion truth

## Human takeover

When a verified human assumes a role:

- `holder_type` becomes `human`
- AI moves to advisory-only posture
- takeover emits a stewardship transfer receipt
- prior AI ticks remain auditable
