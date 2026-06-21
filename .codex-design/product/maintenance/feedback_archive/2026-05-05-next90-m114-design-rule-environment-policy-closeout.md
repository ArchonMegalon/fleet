# next90-m114-design-rule-environment-policy

## Scope

Date: 2026-05-05
Package: `next90-m114-design-rule-environment-policy`
Frontier: `1910967170`
Scope: implementation-only
Owned surfaces:

- `rule_environment_truth`
- `explain_policy:grounded_media`

This slice closes the design-owned truth boundary for rule-environment media companions.
It keeps rule-environment explainers, companion cards, and optional presenter media subordinate to inspectable engine receipts instead of letting polished narration become self-authenticating mechanics.

## What shipped

- `products/chummer/RULE_ENVIRONMENT_GROUNDED_MEDIA_POLICY.md` now defines the product promise, truth order, required receipt floor, fallback posture, localization constraints, and forbidden outcomes for media that talks about rule-environment changes.
- `products/chummer/RULE_ENVIRONMENT_AND_AMEND_SYSTEM.md` now binds rule-environment companions to the same activation and diff receipts, requires visible receipt entry points, and blocks media-only legality review.
- `products/chummer/COMPANION_PACKET.md` now requires rule-environment packets to preserve active or compared environment identity and receipt refs ahead of any optional media layer.
- `products/chummer/COMPANION_TRIGGER_REGISTRY.yaml` now fail-closes `campaign_rules_changed` media posture around required rule-environment truth inputs and forbidden media-only claims.
- `products/chummer/PUBLIC_VIDEO_BRIEFS.yaml` now gives `rule_environment_grounded_companion_video` explicit receipt fields, truth order, fallback siblings, and forbidden modes.
- `products/chummer/STRUCTURED_VIDEO_AND_NARRATED_MEDIA_MODEL.md` now classifies rule-environment grounded media as an optional explain lane that must remain below packet, receipt, and text-fallback truth.
- `products/chummer/LOCALIZATION_AND_LANGUAGE_SYSTEM.md` now keeps locale fallback from paraphrasing away rule-environment receipt identity or recovery posture.
- `scripts/ai/validate_next90_m114_design_rule_environment_policy.py` now fail-closes missing policy markers, linked canon drift, queue or registry drift, and missing machine-readable video or trigger truth fields for this package.
- `scripts/ai/verify.sh` now includes the M114 validator in standard design verification.

## Proof anchors

- `products/chummer/RULE_ENVIRONMENT_GROUNDED_MEDIA_POLICY.md`
- `products/chummer/RULE_ENVIRONMENT_AND_AMEND_SYSTEM.md`
- `products/chummer/COMPANION_PACKET.md`
- `products/chummer/COMPANION_TRIGGER_REGISTRY.yaml`
- `products/chummer/PUBLIC_VIDEO_BRIEFS.yaml`
- `products/chummer/STRUCTURED_VIDEO_AND_NARRATED_MEDIA_MODEL.md`
- `products/chummer/LOCALIZATION_AND_LANGUAGE_SYSTEM.md`
- `products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml`
- `products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml`
- `scripts/ai/validate_next90_m114_design_rule_environment_policy.py`
- `scripts/ai/verify.sh`

## Verification

- `python3 scripts/ai/validate_next90_m114_design_rule_environment_policy.py`
- `bash scripts/ai/verify.sh`

## Do not reopen

Do not reopen this package to add more companion personas, wider presenter styles, or non-rule-environment marketing narration.
Those belong in sibling packages once they need new owned surfaces.

Future shards should verify the proof anchors above, plus the canonical registry and design queue rows, instead of reopening the grounded-media truth-boundary slice.
