# Developer Guide — Global Flagship Audit v4

Source packet: `chummer_global_flagship_audit_20260514_v4.zip`

## Implemented scope

This packet is implemented through three repo slices:

- `chummer6-hub`
- `chummer6-hub-registry`
- `chummer6-design`

## Required technical outcomes

### Public flagship front

- live root must use the Black Ledger flagship landing view
- route proof, responsive proof, and asset-quality proof must remain green

### Public feedback safety

- public `/feedback` must not expose providers, operators, callbacks, secret names, env vars, or delivery internals
- feedback closeout language must stay public-safe and bounded

### Black Ledger maturity

- live page must consume canonical registry seed data
- deterministic turn-two preview must be available
- AI stewardship posts and transfer preview must render publicly
- public map/faction/tick proof must pass

### Ruleset/public release proof

- ruleset classifier must publish
- final janitor and release rehearsal must stay in the verifier stack

## Remaining global-release boundary

If desktop runtime receipt freshness is stale, treat the product as a strong public preview rather than a closed global flagship release, even if the Hub packet itself is green.
