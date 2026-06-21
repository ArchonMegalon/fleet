# M110 Design Runsite Host Bounds closeout

Package: `next90-m110-design-runsite-host-bounds`
Frontier: `2624042542`
Date: `2026-04-23`

## What shipped

The design-owned runsite canon now keeps host mode visibly below route, tour, and pack inspection truth.

Updated runsite-boundary canon:

* `RUNSITE_HOST_MODE_POLICY.md` now defines runsite host mode as preview-safe orientation only, pins the truth order, and requires inspectable route, tour, and pack siblings to stay visible.
* `PUBLIC_VIDEO_BRIEFS.yaml` now gives `runsite_orientation_video` explicit audience variants, locale fallback order, truth order, receipt minimums, fail-closed fallbacks, and forbidden modes that stop clips from becoming tactical authority.
* `MEDIA_ARTIFACT_RECIPE_REGISTRY.yaml`, `STRUCTURED_VIDEO_AND_NARRATED_MEDIA_MODEL.md`, `VIDBOARD_AND_LTD_WOW_FACTOR_WORKFLOWS.md`, `EXTERNAL_TOOLS_PLANE.md`, and `horizons/runsite.md` now agree that runsite host clips are secondary orientation siblings and that route, map, and tour surfaces remain first-party inspectable truth.
* `scripts/ai/validate_next90_m110_design_runsite_host_bounds.py` now fail-closes the package against policy drift, runsite brief drift, recipe drift, verifier wiring drift, and canonical registry/queue drift.

Validation run:

* `python3 scripts/ai/validate_next90_m110_design_runsite_host_bounds.py`

## Do not reopen

Do not reopen this slice for generic runsite polish.
Reopen only when canonical route/tour inspection posture changes or when the validator proves drift in the M110 package anchors.
