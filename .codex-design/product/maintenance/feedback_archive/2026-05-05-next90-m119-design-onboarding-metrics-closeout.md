# next90-m119-design-onboarding-metrics

## Scope

Date: 2026-05-05
Package: `next90-m119-design-onboarding-metrics`
Frontier: `4803543375`
Scope: implementation-only
Owned surfaces:

- `onboarding_metrics`
- `onboarding_claims`

This slice closes the design-owned first-playable-session metrics and bounded
onboarding-claims contract for milestone 119.
It gives the desktop, public no-desktop, recovery, telemetry, and governor
surfaces one shared definition of success instead of letting onboarding claims
float on prose alone.
M119 chummer6-design first-playable-session metrics and bounded onboarding
claims are complete.

## What shipped

- `products/chummer/FIRST_PLAYABLE_SESSION_ONBOARDING_METRICS.md` now defines the first-playable-session success definition, lane stages, scorecard thresholds, allowed claims, forbidden claims, and governor handoff contract for onboarding.
- `products/chummer/PRODUCT_USAGE_TELEMETRY_MODEL.md` now treats first-playable-session onboarding as a first-class funnel with lane-scoped completion, blocker-recovery, and primer-or-briefing coverage measurements.
- `products/chummer/PRODUCT_USAGE_TELEMETRY_EVENT_SCHEMA.md` now defines the exact onboarding event names, canonical onboarding workflow IDs, stage IDs, blocker families, and the `first_playable_session_daily` rollup.
- `products/chummer/PUBLIC_ONBOARDING_PATHS_FOR_NO_DESKTOP_USERS.md` now points public no-desktop entry to the bounded claim contract instead of leaving that lane as open-ended promise copy.
- `products/chummer/README.md` now places the onboarding metrics canon on the main reading path beside public onboarding and telemetry.
- `scripts/ai/validate_next90_m119_design_onboarding_metrics.py` now fail-closes missing onboarding metric markers, telemetry-schema drift, public-claim drift, and queue or registry proof drift for this package.
- `scripts/ai/verify.sh` now includes the M119 validator in standard design verification.

## Proof anchors

- `products/chummer/FIRST_PLAYABLE_SESSION_ONBOARDING_METRICS.md`
- `products/chummer/PRODUCT_USAGE_TELEMETRY_MODEL.md`
- `products/chummer/PRODUCT_USAGE_TELEMETRY_EVENT_SCHEMA.md`
- `products/chummer/PUBLIC_ONBOARDING_PATHS_FOR_NO_DESKTOP_USERS.md`
- `products/chummer/README.md`
- `products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml`
- `products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml`
- `scripts/ai/validate_next90_m119_design_onboarding_metrics.py`
- `scripts/ai/verify.sh`

## Verification

- `python3 scripts/ai/validate_next90_m119_design_onboarding_metrics.py`

## Do not reopen

Do not reopen this package to add retention theory, monetization funnels, or
future public launch-health dashboards.
Those belong in milestone 120 or later once they need new owned surfaces.

Future shards should verify the proof anchors above, plus the canonical
registry, the local design queue row, and the published fleet queue row,
instead of reopening the onboarding-metrics and claim-boundary slice.
