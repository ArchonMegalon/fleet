Title: Shard 4 flagship hub, registry, and front-door audit

Run context:
- run: `20260414T233531Z-shard-4`
- frontier: `2541792707`
- scope: `Full Chummer5A parity and flagship proof closeout`
- date: `2026-04-14`

Result:
- The assigned hub/registry/front-door slice is locally aligned with canonical design and published release truth.
- No local repo change was warranted in this pass because the only remaining release-proof blocker is still the external native macOS tuple `avalonia:osx-arm64:macos`.
- Published readiness must remain fail-closed until that host proof is freshly captured, ingested, and republished.

Evidence:
- `/var/lib/codex-fleet/chummer_design_supervisor/shard-4/runs/20260414T233531Z-shard-4/TASK_LOCAL_TELEMETRY.generated.json`
  - reports one remaining open milestone and outstanding readiness coverage only on `desktop_client`
- `/var/lib/codex-fleet/chummer_design_supervisor/shard-4/ACTIVE_RUN_HANDOFF.generated.md`
  - scopes this worker to the flagship hub/registry/front-door finish and requires no republish until repo truth justifies it
- `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
  - still reports `status=fail` with `warning_keys=["desktop_client"]`
  - completion audit remains `external_only=true` with unresolved tuple `avalonia:osx-arm64:macos`
- `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
  - still points the only host backlog at macOS and marks the cached bundle as stale
- `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`
  - still publishes the current shelf honestly with `rolloutState="coverage_incomplete"` and missing tuple coverage only for `avalonia:osx-arm64:macos`
- `/docker/chummercomplete/chummer-design/products/chummer/PUBLIC_RELEASE_EXPERIENCE.yaml`
  - still requires one guided installer path, in-product claim/restore handling, and no overclaiming beyond proven flagship acceptance
- `/docker/chummercomplete/chummer-design/products/chummer/projects/hub.md`
  - keeps `chummer.run` public landing, downloads, support, and signed-in overlays inside hub scope
- `/docker/chummercomplete/chummer-design/products/chummer/projects/hub-registry.md`
  - keeps promoted desktop release-head truth and install/update metadata inside registry scope

Verification:
- Command:
  - `cd /docker/fleet && python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir .codex-studio/published/external-proof-commands --json`
- Result:
  - failed only on the expected external backlog
  - unresolved host: `macos`
  - unresolved tuple: `avalonia:osx-arm64:macos`
  - release channel still missing only `macos`, `avalonia:macos`, and `avalonia:osx-arm64:macos`
- Command:
  - `cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json`
- Result:
  - passed
  - current published registry truth is internally consistent and already fail-closed on the missing macOS proof

Conclusion:
- The assigned slice does not have a hidden local implementation gap left to close from this Linux worker.
- The only honest next step is external host execution, not local republishing or relaxed readiness truth.

Exact next action:
- Run `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh` on a native macOS host for `avalonia:osx-arm64:macos`.
- Ingest the fresh bundle with `/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`.
- Republish readiness only after the new receipt clears the release-channel and flagship-product-readiness gates.
