# Next90 M133.7 Fleet media/social horizon monitors

- package_id: `next90-m133-fleet-monitor-media-social-horizon-proof-freshness-consent-gat`
- frontier_id: `2336165027`
- status: `blocked`

## What landed

- added the Fleet M133 materializer and verifier for media/social horizon canon, consent gates, publication proof freshness, unsupported-claim posture, and provider-health stop conditions
- added focused tests covering canonical drift, runtime blockers, and nested release-proof freshness
- generated the live Fleet packet and markdown artifact

## Live blockers surfaced

- all six target media/social horizons in `HORIZON_REGISTRY.yaml` still lack `allowed_surfaces`
- all six target media/social horizons still lack `proof_gate`
- all six target media/social horizons still lack `public_claim_posture`
- all six target media/social horizons still lack `stop_condition`

## Live warnings surfaced

- `RELEASE_CHANNEL.generated.json` is fresh, but its nested `releaseProof.generatedAt` is stale beyond the 48h threshold
- provider fallback coverage remains thin for `core`, `core_authority`, `core_booster`, `core_rescue`, and `groundwork`
- governor posture is still `freeze_launch` with `rollback` armed
