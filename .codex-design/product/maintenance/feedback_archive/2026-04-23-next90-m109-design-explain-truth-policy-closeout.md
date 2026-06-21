# next90-m109-design-explain-truth-policy

## Scope

Date: 2026-04-23
Package: `next90-m109-design-explain-truth-policy`
Frontier: `1886875416`
Scope: implementation-only
Owned surfaces:

- `build_explain_policy`
- `inspectable_engine_truth:artifact_claims`

This slice closes the design-owned claim-bounding policy for Build and Explain companion artifacts.
It keeps rendered companions below inspectable engine packets, receipt anchors, packet revisions, and approval-scope truth instead of letting polished media posture become self-authenticating.

## What shipped

- `products/chummer/BUILD_EXPLAIN_ARTIFACT_TRUTH_POLICY.md` now defines receipt and anchor minimums, explicit packet-revision and rule-environment traceability, approval-scope limits, and fail-closed fallback when those truth inputs are missing.
- `products/chummer/BUILD_LAB_PRODUCT_MODEL.md` now requires Build Lab companions to preserve the exact packet revision, rule-environment identity, anchor scope, and approval scope they summarize.
- `products/chummer/STRUCTURED_VIDEO_AND_NARRATED_MEDIA_MODEL.md` now states that Build and Explain narration cannot ship unless revision identity, anchor scope, and approval scope remain inspectable.
- `products/chummer/PUBLIC_VIDEO_BRIEFS.yaml` now gives `build_explain_companion_video` explicit required receipt fields, approval-scope axes, revision-mismatch forbiddance, and fail-closed fallback siblings.
- `products/chummer/LOCALIZATION_AND_LANGUAGE_SYSTEM.md` now prevents locale fallback from rewriting packet revision ids, approval-state labels, or rule-environment badges into freer marketing-style narration.
- `scripts/ai/validate_next90_m109_design_explain_truth_policy.py` now fail-closes missing receipt-floor markers, missing closure metadata, queue or registry drift, and missing Build and Explain video-brief truth fields for this package.
- `scripts/ai/verify.sh` continues to include the M109 Build and Explain policy doc and validator in standard design-repo verification.

## Proof anchors

- `products/chummer/BUILD_EXPLAIN_ARTIFACT_TRUTH_POLICY.md`
- `products/chummer/BUILD_LAB_PRODUCT_MODEL.md`
- `products/chummer/STRUCTURED_VIDEO_AND_NARRATED_MEDIA_MODEL.md`
- `products/chummer/PUBLIC_VIDEO_BRIEFS.yaml`
- `products/chummer/LOCALIZATION_AND_LANGUAGE_SYSTEM.md`
- `products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml`
- `products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml`
- `scripts/ai/validate_next90_m109_design_explain_truth_policy.py`
- `scripts/ai/verify.sh`

## Verification

- `python3 scripts/ai/validate_next90_m109_design_explain_truth_policy.py`
- `bash scripts/ai/verify.sh`

## Do not reopen

Do not reopen this package to add more media families, new narration styles, or broader Build Lab marketing copy.
Those belong in sibling packages once they need new owned surfaces.

Future shards should verify the proof anchors above, plus the canonical registry and design queue rows, instead of reopening the inspectable-engine-truth claim-bounding slice.
