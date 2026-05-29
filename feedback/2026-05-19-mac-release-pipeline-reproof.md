# Mac release pipeline reproof

Goal: prove the mac public release path end to end after the late manifest-validation fixes, instead of treating source patches as equivalent to a shipped green publish run.

Why this is still open:
- fresh mac release attempts on 2026-05-19 repeatedly reached build, DMG packaging, startup smoke, and manifest generation
- upload never started because local manifest validation failed late on verifier-owned release-channel drift:
  - `desktopTupleCoverage.externalProofRequests does not match missing desktop tuple coverage`
  - `desktopSurfaceRefs does not match canonical desktop surface truth`
- both generator paths have now been hardened:
  - `/docker/chummercomplete/chummer-presentation/scripts/generate-releases-manifest.sh`
  - `/docker/chummercomplete/chummer.run-services/scripts/generate-releases-manifest.sh`
- but there is not yet a fresh successful publish receipt from a rerun using those fixes

Required closure:
- rerun the mac release path from current `main`
- confirm local manifest validation passes
- confirm upload starts and completes
- refresh the published shelf/proof bundle from that successful run

Primary sources:
- `/docker/chummercomplete/chummer-presentation/scripts/generate-releases-manifest.sh`
- `/docker/chummercomplete/chummer.run-services/scripts/generate-releases-manifest.sh`
- `/docker/chummercomplete/chummer-hub-registry/scripts/verify_public_release_channel.py`

Exit condition:
- a fresh mac release run completes through upload on the current sources
- release-path closure can point at a successful end-to-end publish run, not only source-level fixes
