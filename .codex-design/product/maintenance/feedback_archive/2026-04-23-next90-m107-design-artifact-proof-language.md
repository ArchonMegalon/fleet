# next90-m107-design-artifact-proof-language

Date: 2026-04-23
Package: `next90-m107-design-artifact-proof-language`
Frontier: `3640572293`
Owned surfaces:

* `artifact_policy:public_proof_shelf`
* `artifact_policy:flagship_claims`

Implemented boundary:

* public proof language is limited to posted files, named flows, and recent checks that a person can inspect today
* preview language may invite real use, but it must stay visibly below flagship wording
* fallback language must name compatibility, recovery, or backup posture explicitly
* artifact-factory cards, captions, packet siblings, and explainers may deepen inspection, but they cannot become the recommended install route or a proxy flagship claim

Touched sources:

* `products/chummer/PUBLIC_LANDING_POLICY.md`
* `products/chummer/PUBLIC_DOWNLOADS_POLICY.md`
* `products/chummer/PUBLIC_RELEASE_EXPERIENCE.yaml`
* `products/chummer/PUBLIC_LANDING_MANIFEST.yaml`
* `products/chummer/FLAGSHIP_PRODUCT_BAR.md`
* `products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml`
* `products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml`
* `products/chummer/public-guide/DOWNLOAD.md`
* `products/chummer/public-guide/README.md`
* `products/chummer/public-guide/FROM_CHUMMER5A_TO_CHUMMER6.md`
* `scripts/ai/materialize_public_guide_bundle.py`
* `tests/test_materialize_public_guide_bundle.py`

Verification:

* `python3 scripts/ai/materialize_public_guide_bundle.py --repo-root /docker/chummercomplete/chummer6-design`
* `python3 scripts/ai/materialize_public_guide_bundle.py --repo-root /docker/chummercomplete/chummer6-design --check`
* `python3 -m pytest tests/test_materialize_public_guide_bundle.py`
