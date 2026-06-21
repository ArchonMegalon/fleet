# guide

## Purpose
`Chummer6` is the downstream human guide repo for the Chummer6 program.

## Rules
- human-only
- downstream-only
- not canonical design
- not the primary public landing surface
- not a queue source
- not a contract source
- not a milestone source
- not mirrored into code repos
- not dispatchable
- generated guide surfaces must include a "How can I help?" or equivalent support page that introduces boosters and links to the Hub participation endpoint

## Allowed inputs
- `PUBLIC_GUIDE_PAGE_REGISTRY.yaml`
- `PUBLIC_PART_REGISTRY.yaml`
- `PUBLIC_FAQ_REGISTRY.yaml`
- `PUBLIC_HELP_COPY.md`
- `PUBLIC_GUIDE_EXPORT_MANIFEST.yaml`
- `PUBLIC_LANDING_MANIFEST.yaml`
- `PUBLIC_FEATURE_REGISTRY.yaml`
- `PUBLIC_USER_MODEL.md`
- generated release matrix artifact
- `HORIZON_REGISTRY.yaml`
- the latest approved public program status
- owning repo READMEs only when the page class explicitly allows them

## Priority order
If `Chummer6` disagrees with canonical sources, fix `Chummer6`.

1. `chummer6-design`
2. page-specific public registries and manifests
3. latest public program status
4. explicitly allowed owning repo sources
5. `Chummer6`

## Out of scope
- code
- tests
- scripts
- runtime instructions
- queue files
- contract files
- milestone authority
- ADR authorship
- review-template authorship
- using raw implementation-scope ownership bullets as first-layer public part-page prose
