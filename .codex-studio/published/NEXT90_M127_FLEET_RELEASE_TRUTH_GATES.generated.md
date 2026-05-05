# Fleet M127 release-truth gates

- status: pass
- package_id: next90-m127-fleet-promote-platform-acceptance-release-evidence-packs-repo
- frontier_id: 6924107419
- generated_at: 2026-05-05T21:29:39Z

## Gate summary
- external proof unresolved requests: 0
- flagship status: fail

## Platform posture
- windows: promoted_preview / installer / in_app_apply_helper
- linux: preview_support_directed / deb / in_app_or_installer_handoff
- macOS: account_gated_setup_script_preview / setup_script / claimed_setup_script_then_dmg_handoff

## Package closeout
- state: pass
- warnings:
  - Acceptance matrix keeps linux in preview_support_directed posture instead of a promoted public lane.
  - Acceptance matrix keeps macOS in account_gated_setup_script_preview posture instead of a promoted public lane.
  - Repo hardening initiative RH-001 is still proposed.
  - Repo hardening initiative RH-002 is still proposed.
  - Repo hardening initiative RH-003 is still proposed.
  - Repo hardening initiative RH-005 is still proposed.
  - Repo hardening initiative RH-006 is still proposed.
  - flagship_product_readiness: Flagship readiness status is fail.
  - flagship_product_readiness: Flagship readiness scoped_status is fail.
