# M127.4 Fleet release-truth gates

- package: `next90-m127-fleet-promote-platform-acceptance-release-evidence-packs-repo`
- status: shipped
- date: `2026-05-05`

## What landed

- Added a live `NEXT90_M127_FLEET_RELEASE_TRUTH_GATES` packet and verifier for release-truth, platform-acceptance, public-downloads, auto-update, repo-hardening, external-proof, and flagship-readiness gate posture.
- Canonical queue, registry, and guide alignment are now checked in one repeatable Fleet packet.
- Runtime gate posture is separated from package health so live preview or hardening warnings do not masquerade as implementation failure.
- Hardened the packet against append-style generated queue overlays so live queue mirrors no longer false-fail as missing rows.

## Audit refinements

- Split structural package blockers from live release-gate failures.
- Corrected the packet dependency contract to match the canonical `127` milestone dependency set.
- Kept preview-platform and proposed-hardening posture as warnings instead of false blockers.

## Live posture

- generated artifact: `.codex-studio/published/NEXT90_M127_FLEET_RELEASE_TRUTH_GATES.generated.json`
- verifier: pass
- release gate status: `blocked`
- blocker count: `0`

Current warnings are real but non-blocking:

- Linux remains `preview_support_directed`
- macOS remains `account_gated_setup_script_preview`
- repo-hardening initiatives `RH-001`, `RH-002`, `RH-003`, `RH-005`, and `RH-006` are still `proposed`
- flagship readiness still reports `fail` / `fail` for the release-truth chain even though this Fleet-owned package is structurally closed
