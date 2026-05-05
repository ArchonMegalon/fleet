# M128.5 Fleet trust-plane monitors

- package: `next90-m128-fleet-add-freshness-and-contradiction-monitors-for-telemetry-p`
- status: shipped
- date: `2026-05-05`

## What landed

- Added a live `NEXT90_M128_FLEET_TRUST_PLANE_MONITORS` packet and verifier for localization, telemetry, privacy, retention, support, and crash trust planes.
- The packet now checks canonical queue and registry alignment, telemetry/privacy/support canon markers, localization shipping-locale parity, and support/feedback-loop counter drift across support packets, weekly pulse, and flagship readiness.
- Runtime trust-plane posture is reported separately from package health so stale source mirrors or refresh failures surface as warnings instead of false implementation failure.

## Audit refinements

- Made freshness calculations deterministic off the packet `generated_at` so the standalone verifier can reproduce the live payload exactly.
- Relaxed canon markers to the actual design-owned phrasing where the guide and telemetry model are intentionally shorter than the registry exit prose.
- Kept source-mirror fallback and remote refresh failure as live warnings rather than package blockers.

## Live posture

- generated artifact: `.codex-studio/published/NEXT90_M128_FLEET_TRUST_PLANE_MONITORS.generated.json`
- verifier: pass
- trust plane status: `warning`
- runtime blocker count: `0`
- warning count: `2`

Current live warnings:

- support packets are using `source_mirror_fallback`
- the remote support-case source at `http://host.docker.internal:8091/api/v1/support/cases/triage` is currently refusing connections
