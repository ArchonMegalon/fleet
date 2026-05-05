# M120 Fleet launch pulse progress

Package: `next90-m120-fleet-launch-pulse`
Owned surfaces: `launch_pulse`, `adoption_health:governor`

The Fleet-owned M120 launch-pulse packet now materializes and verifies cleanly from the governed source packets.

- `scripts/materialize_next90_m120_fleet_launch_pulse.py` now accepts both the real staged-queue shape and a direct queue-row fixture, and it counts stale versus missing proof inputs separately instead of inflating `missing_input_count`.
- `scripts/verify_next90_m120_fleet_launch_pulse.py` continues to fail closed on packet drift while the refreshed artifact proves the current queue, registry, launch-action, adoption-health, support-risk, proof-freshness, and public-followthrough contract.
- `tests/test_materialize_next90_m120_fleet_launch_pulse.py` and `tests/test_verify_next90_m120_fleet_launch_pulse.py` now match the real queue-row structure and verifier error text.
- `.codex-studio/published/NEXT90_M120_FLEET_LAUNCH_PULSE.generated.json` and `.md` were refreshed from the current weekly governor packet, weekly product pulse, support packets, progress report, flagship readiness, journey gates, proof orchestration, and status-plane truth.

Current proof:

- Packet `status` is `pass`.
- `proof_freshness.state` is `pass` with `missing_input_count: 0` and `stale_input_count: 0`.
- The standalone verifier passes against the refreshed published artifact.

Verification:

- `python3 -m unittest tests.test_materialize_next90_m120_fleet_launch_pulse tests.test_verify_next90_m120_fleet_launch_pulse`
- `python3 scripts/verify_next90_m120_fleet_launch_pulse.py --artifact /docker/fleet/.codex-studio/published/NEXT90_M120_FLEET_LAUNCH_PULSE.generated.json --successor-registry /docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml --queue-staging /docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml --design-queue-staging /docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml --weekly-governor-packet /docker/fleet/.codex-studio/published/WEEKLY_GOVERNOR_PACKET.generated.json --weekly-product-pulse /docker/chummercomplete/chummer-design/products/chummer/WEEKLY_PRODUCT_PULSE.generated.json --support-packets /docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --progress-report /docker/fleet/.codex-studio/published/PROGRESS_REPORT.generated.json --flagship-readiness /docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json --journey-gates /docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json --proof-orchestration /docker/fleet/.codex-studio/published/PROOF_ORCHESTRATION.generated.json --status-plane /docker/fleet/.codex-studio/published/STATUS_PLANE.generated.yaml --json`
