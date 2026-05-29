# Fleet M127 release-truth gates

- status: pass
- package_id: next90-m127-fleet-promote-platform-acceptance-release-evidence-packs-repo
- frontier_id: 6924107419
- generated_at: 2026-05-13T17:14:00Z

## Gate summary
- external proof unresolved requests: 0
- flagship status: pass

## Platform posture
- windows: promoted_release / installer / in_app_apply_helper
- linux: support_directed_release / deb / in_app_or_installer_handoff
- macOS: account_gated_setup_script_release / setup_script / claimed_setup_script_then_dmg_handoff

## Package closeout
- state: pass
- warnings:
  - Acceptance matrix keeps linux in support_directed_release posture instead of a promoted public lane.
  - Acceptance matrix keeps macOS in account_gated_setup_script_release posture instead of a promoted public lane.
  - Repo hardening initiative RH-001 is still proposed.
  - Repo hardening initiative RH-002 is still proposed.
  - Repo hardening initiative RH-003 is still proposed.
  - Repo hardening initiative RH-005 is still proposed.
  - Repo hardening initiative RH-006 is still proposed.
