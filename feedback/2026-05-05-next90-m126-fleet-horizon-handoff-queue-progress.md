# M126.2 Fleet horizon handoff queue guard

- package: `next90-m126-fleet-teach-the-supervisor-to-stage-bounded-horizon-conversion`
- status: shipped
- date: `2026-05-05`

## What landed

- Supervisor queue selection now blocks horizon-conversion packages until design task `126.1` is done.
- Horizon-conversion packages also stay blocked when the horizon registry is missing, when `owning_repos` are missing, or when the owning repo still lacks required handoff fields.
- Fleet now publishes a live `NEXT90_M126_FLEET_HORIZON_HANDOFF_QUEUE` packet plus verifier coverage.

## Audit refinements

- Added fail-closed handling for a missing `HORIZON_REGISTRY.yaml`.
- Added fail-closed handling for horizons that cannot be attributed to an owning repo.
- Added focused regression tests for design-gate, incomplete-registry, and missing-registry cases.
- Hardened append-style queue overlay parsing so live queue mirrors no longer false-fail as missing rows when the guard recomputes its canonical alignment.

## Live posture

- generated artifact: `.codex-studio/published/NEXT90_M126_FLEET_HORIZON_HANDOFF_QUEUE.generated.json`
- verifier: pass
- live blocked horizon queue items: `20`
- live ready horizon queue items: `0`
- live design gate task status: `unknown`

The packet is passing because the guardrail is in place. The current blocked posture is expected until design-owned handoff canon becomes complete.
