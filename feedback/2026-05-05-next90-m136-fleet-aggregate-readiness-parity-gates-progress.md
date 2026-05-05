# Next90 M136.6 Fleet aggregate-readiness parity gates

- package_id: `next90-m136-fleet-fail-closed-on-aggregate-readiness-when-family-level-parity-proof-sub`
- frontier_id: `2277811964`
- package status: `pass`
- live monitor status: `blocked`

## What landed

- added the Fleet M136 materializer and verifier for aggregate-readiness parity proof, screenshot-pack freshness, continuity receipt freshness, and aggregate-green contradiction detection
- wired flagship aggregate readiness to fail closed when the M136 gate is missing or runtime-blocked, instead of letting structural green masquerade as veteran-continuity closure
- added focused tests for runtime blocker separation, canonical parity-matrix coverage, verifier drift, and the flagship readiness helper

## Live findings

- the live M136 packet now passes as a package and blocks runtime truth exactly where the current product proof is still incomplete
- the current direct blockers are:
  - `CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json` is stale at `73.29h`
  - `CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json` is stale at `73.29h`
  - `DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json` is not passing
  - `CAMPAIGN_OS_CONTINUITY_LIVENESS.generated.json` is not passing
  - `FLAGSHIP_PRODUCT_READINESS.generated.json` was still green before this gate was wired in
- the Fleet queue mirror row for `136.6` is still missing, but it is now a warning instead of a false aggregate-readiness blocker because the design queue remains authoritative

## Aggregate readiness effect

- a temp-materialized flagship readiness payload now fails closed
- `readiness_planes.flagship_ready.status=warning`
- `readiness_planes.flagship_ready.reasons=["M136 aggregate-readiness parity gate is not ready."]`
