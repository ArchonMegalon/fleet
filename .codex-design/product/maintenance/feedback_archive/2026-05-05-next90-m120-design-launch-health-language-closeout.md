# Next90 Successor Wave Closeout: next90-m120-design-launch-health-language

## Scope

Milestone: **120**
Package ID: **next90-m120-design-launch-health-language**
Frontier ID: **1708070943**
Owner: **chummer6-design**
Status at landing: **complete**

## Outcome

Public launch-health language was tightened so public-facing channels use the exact posture set:
`live`, `preview`, `fallback`, `fixed`, `revoked`, and `blocked` without drift.
The package now explicitly binds release-copy posture, auto-update policy wording, help/trust guidance, and download-facing copy so that:

- Blocked and withdrawn routes are not treated as recommended/recommended-like.
- Fallback routes remain visible and operational without being positioned as `live`.
- `fixed` claims are reserved for routes/versions where availability is actually true.

## Proof anchors

- `/docker/chummercomplete/chummer6-design/products/chummer/PUBLIC_LAUNCH_HEALTH_LANGUAGE.md`
- `/docker/chummercomplete/chummer6-design/products/chummer/PUBLIC_RELEASE_EXPERIENCE.yaml`
- `/docker/chummercomplete/chummer6-design/products/chummer/PUBLIC_AUTO_UPDATE_POLICY.md`
- `/docker/chummercomplete/chummer6-design/products/chummer/PUBLIC_HELP_COPY.md`
- `/docker/chummercomplete/chummer6-design/products/chummer/PUBLIC_TRUST_CONTENT.yaml`
- `/docker/chummercomplete/chummer6-design/products/chummer/public-guide/DOWNLOAD.md`
- `/docker/chummercomplete/chummer6-design/products/chummer/README.md`
- `/docker/chummercomplete/chummer6-design/scripts/ai/validate_next90_m120_design_launch_health_language.py`
- `/docker/chummercomplete/chummer6-design/scripts/ai/verify.sh`
- `/docker/chummercomplete/chummer6-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml`
- `/docker/chummercomplete/chummer6-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml`

## Registry and queue lock

- Registry work task `120.5` is marked complete and cites this closeout evidence set.
- Local and published queue row for `next90-m120-design-launch-health-language` are marked complete with `completion_action: verify_closed_package_only`.
- `do_not_reopen_reason` requires future shards to verify lock state via registry+queue proofs and skip redesigning this slice.

## Verification posture

- The package includes `validate_next90_m120_design_launch_health_language.py` to guard against drift in the launch-health vocabulary and closed-package proof rows.
- The validator is wired into standard design verification via `scripts/ai/verify.sh`.

## Release posture commitments preserved

- Public release copy continues to label preview, fallback, blocked, and revoked states clearly.
- Support and recovery paths remain distinguishable from fixed/primary routes.
- Public download guidance remains explicit about what is live vs fallback and avoids overpromising.
