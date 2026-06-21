# next90-m117-design-artifact-shelf-policy

## Scope

Date: 2026-05-05
Package: `next90-m117-design-artifact-shelf-policy`
Frontier: `3777712364`
Scope: implementation-only
Owned surfaces:

- `artifact_shelf_policy`
- `shelf_truth_boundaries`

This slice closes the design-owned artifact shelf boundary for personal, campaign, creator, and public views.
It keeps shelf presentation subordinate to audience posture, locale posture, retention posture, and inspectable source truth.
M117 chummer6-design artifact shelf policy is complete.

## What shipped

- `products/chummer/ARTIFACT_SHELF_POLICY.md` now defines the truth order, required shelf facets, audience rules, locale rules, retention rules, inspectable sibling actions, per-shelf-family boundaries, and forbidden modes for personal, campaign, creator, and public artifact shelves.
- `products/chummer/CAMPAIGN_WORKSPACE_AND_DEVICE_ROLES.md` now routes campaign-facing artifact shelves through the new policy so recap, primer, and briefing cards keep safer audience fallback, retention posture, and inspectable source actions visible.
- `products/chummer/CREATOR_OPERATING_SYSTEM.md` now points creator-owned shelves back to the new policy whenever locale, retention, inspectable source truth, or public-versus-creator audience boundaries matter.
- `products/chummer/PUBLIC_DOWNLOADS_POLICY.md` now requires proof-gallery artifacts beside `/downloads` install truth to keep audience, locale, retention, and inspectable-source posture visible instead of blurring into release authority.
- `products/chummer/LOCALIZATION_AND_LANGUAGE_SYSTEM.md` now binds artifact-shelf labels, captions, packet siblings, retention badges, and inspectable sibling actions to one deterministic locale chain and blocks fallback copy from hiding shelf truth posture.
- `products/chummer/README.md` now places the artifact shelf policy on the main canon reading path beside the downloads and localization policy.
- `scripts/ai/validate_next90_m117_design_artifact_shelf_policy.py` now fail-closes missing policy markers, linked campaign/creator/public/localization canon drift, and registry or queue proof drift for this package.
- `scripts/ai/verify.sh` now includes the M117 validator in standard design verification.

## Proof anchors

- `products/chummer/ARTIFACT_SHELF_POLICY.md`
- `products/chummer/CAMPAIGN_WORKSPACE_AND_DEVICE_ROLES.md`
- `products/chummer/CREATOR_OPERATING_SYSTEM.md`
- `products/chummer/PUBLIC_DOWNLOADS_POLICY.md`
- `products/chummer/LOCALIZATION_AND_LANGUAGE_SYSTEM.md`
- `products/chummer/README.md`
- `products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml`
- `products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml`
- `scripts/ai/validate_next90_m117_design_artifact_shelf_policy.py`
- `scripts/ai/verify.sh`

## Verification

- `python3 scripts/ai/validate_next90_m117_design_artifact_shelf_policy.py`
- `bash scripts/ai/verify.sh`

## Do not reopen

Do not reopen this package to invent new shelf families, archive products, or broader publication heuristics.
Those belong in sibling packages once they need new owned surfaces.

Future shards should verify the proof anchors above, plus the canonical registry and design queue rows, instead of reopening the shelf-policy honesty slice.
