# next90-m108-design-campaign-briefing-canon

## Scope

Package: `next90-m108-design-campaign-briefing-canon`
Frontier: `1728354534`
Owned surfaces:

- `campaign_os:artifact_promise`
- `campaign_os:audience_locale_rules`

This slice closes the design-owned canon for campaign cold-open and mission-briefing artifacts.
It makes those artifacts first-class campaign OS promises while keeping them bounded by audience class, locale fallback, and spoiler-safe launch rules.

## What shipped

- `products/chummer/CAMPAIGN_COLD_OPEN_AND_MISSION_BRIEFING_POLICY.md` now defines the product promise, audience classes, locale chain, spoiler discipline, launch contract, and non-goals for `campaign_cold_open` and `mission_briefing`.
- `products/chummer/CAMPAIGN_WORKSPACE_AND_DEVICE_ROLES.md` now treats campaign cold-open cards and mission briefings as first-class workspace outputs only when audience, locale, and source-pack posture remain visible.
- `products/chummer/LOCALIZATION_AND_LANGUAGE_SYSTEM.md` now binds campaign artifact captions, preview copy, sibling packets, and text fallback to the deterministic `requested -> campaign default -> en-US` locale chain.
- `products/chummer/PUBLIC_VIDEO_BRIEFS.yaml` now gives `campaign_primer_video` and `mission_brief_video` explicit audience variants, spoiler classes, launch surfaces, locale fallback chains, and localized text fallback siblings.
- `scripts/ai/validate_next90_m108_design_campaign_briefing_canon.py` now fail-closes missing canon anchors, queue or registry drift, and missing audience or locale metadata for this package.
- `scripts/ai/verify.sh` now includes the M108 campaign briefing canon doc and validator in standard repo verification.

## Proof anchors

- `products/chummer/CAMPAIGN_COLD_OPEN_AND_MISSION_BRIEFING_POLICY.md`
- `products/chummer/CAMPAIGN_WORKSPACE_AND_DEVICE_ROLES.md`
- `products/chummer/LOCALIZATION_AND_LANGUAGE_SYSTEM.md`
- `products/chummer/PUBLIC_VIDEO_BRIEFS.yaml`
- `products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml`
- `products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml`
- `scripts/ai/validate_next90_m108_design_campaign_briefing_canon.py`
- `scripts/ai/verify.sh`

## Verification

- `python3 scripts/ai/validate_next90_m108_design_campaign_briefing_canon.py`
- `bash scripts/ai/verify.sh`

## Do not reopen

Do not reopen this package to add more cinematic variants, public teaser behavior, runsite orientation, or GM-private briefing expansion.
Those belong in sibling packages once they need new owned surfaces.

Future shards should verify the proof anchors above, plus the canonical registry and design queue rows, instead of reopening the audience-locale spoiler-safe canon slice.
