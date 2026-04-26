# M111 Fleet install-aware followthrough progress

Date: 2026-04-23
Package: `next90-m111-fleet-install-aware-followthrough`
Frontier: `5200108449`

This shard adds a Fleet-local generated receipt and standalone verifier for the open `111.4` slice instead of reopening any closed flagship or predecessor package.

Shipped in this pass:

- `scripts/materialize_next90_m111_fleet_install_aware_followthrough.py` now compiles one package-scoped gate artifact from:
  - `SUPPORT_CASE_PACKETS.generated.json`
  - `WEEKLY_GOVERNOR_PACKET.generated.json`
  - mirrored `WEEKLY_PRODUCT_PULSE.generated.json`
  - mirrored `PROGRESS_REPORT.generated.json`
  - canonical successor registry and Fleet queue staging
- `scripts/verify_next90_m111_fleet_install_aware_followthrough.py` fail-closes drift between the generated M111 artifact and the source receipt/promotion/public-proof inputs.
- `scripts/verify_next90_m111_fleet_install_aware_followthrough.py` now also fail-closes canonical package-scope drift even after regeneration: the verifier rejects M111 artifacts whose `agreement.queue_scope_matches_package` or `agreement.registry_scope_matches_package` fields are false.
- Regression coverage now proves the verifier rejects stale published M111 artifacts after the install-aware support packet or weekly governor packet is regenerated, even when the pulse and progress mirrors stay unchanged.
- Bootstrap coverage now includes the new M111 materializer and verifier with no `PYTHONPATH` dependency.
- Regression tests cover the green path, publication-ref drift, support/governor source-refresh drift, and regenerated queue-scope drift.
- `.codex-studio/published/NEXT90_M111_FLEET_INSTALL_AWARE_FOLLOWTHROUGH.generated.json` has been refreshed against the current install-aware support packet, weekly governor packet, weekly product pulse, and mirrored progress report so the published receipt matches repo-local evidence again.

Current package posture after this shard:

- Fleet can now prove whether followthrough mail is clear from install-aware receipt truth.
- Fleet can now prove whether public-proof promotion is clear only when receipt blockers are zero, weekly launch truth agrees, public-status posture agrees, and the publication refs share one public snapshot date.
- Fleet now fail-closes the package if canonical queue scope or registry work-task scope drifts, even when the published M111 gate artifact is regenerated from the drifted inputs.
- The package is not closed by this note alone; downstream queue/registry proof markers and any further generated-packet promotion wiring still need honest followthrough before closeout.
