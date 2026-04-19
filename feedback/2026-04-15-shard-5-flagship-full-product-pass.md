Title: Shard 5 flagship full-product delivery pass

Run context:
- run: `20260415T013038Z-shard-5`
- frontier: `1300044932`
- scope: `Full Chummer5A parity and flagship proof closeout`
- date: `2026-04-15`

Result:
- The assigned flagship slice still matches canonical design, published readiness truth, and the worker-safe runtime handoff.
- No local implementation, mirror, or publication edit was justified in this pass because the only remaining readiness blocker is still the external native macOS tuple `avalonia:osx-arm64:macos`.
- Published readiness must remain fail-closed until a fresh native-host startup-smoke receipt is captured, ingested, and then used to republish release truth.

Evidence:
- `/var/lib/codex-fleet/chummer_design_supervisor/shard-5/runs/20260415T013038Z-shard-5/TASK_LOCAL_TELEMETRY.generated.json`
  - still reports one remaining open milestone and outstanding readiness coverage only on `desktop_client`
- `/var/lib/codex-fleet/chummer_design_supervisor/shard-5/ACTIVE_RUN_HANDOFF.generated.md`
  - still constrains the run to the flagship frontier and requires readiness to stay fail-closed until `FLAGSHIP_PRODUCT_READINESS.generated.json` is green
- `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`
  - still reports `status=fail`
  - `missing_keys=["desktop_client"]`
  - completion audit remains external-only with unresolved tuple `avalonia:osx-arm64:macos`
- `/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md`
  - still requests only the macOS host lane
  - marks the cached macOS bundle as stale
- `/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
  - is still the April 11 receipt
  - `recordedAtUtc="2026-04-11T20:19:47.089302+00:00"`
- `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`
  - still publishes the shelf honestly with `rolloutState="coverage_incomplete"`
  - missing tuple coverage remains limited to `avalonia:osx-arm64:macos`
- `/docker/chummercomplete/chummer-design/products/chummer/PUBLIC_RELEASE_EXPERIENCE.yaml`
  - still requires the guided Chummer installer path, workbench/restore-first startup, and no browser-only claim ritual

Verification:
- Command:
  - `cd /docker/fleet/.codex-studio/published/external-proof-commands && ./validate-macos-proof.sh`
- Result:
  - failed with `startup-smoke-receipt-stale:/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json:age_seconds=277961:max_age_seconds=86400`
- Command:
  - `cd /docker/fleet && python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir .codex-studio/published/external-proof-commands --json`
- Result:
  - failed only on the expected external backlog
  - unresolved host: `macos`
  - unresolved tuple: `avalonia:osx-arm64:macos`
  - journey gates still block externally on `install_claim_restore_continue`, `organize_community_and_close_loop`, and `report_cluster_release_notify`
- Command:
  - `cd /docker/fleet && python3 scripts/materialize_flagship_product_readiness.py --out /tmp/flagship-readiness-shard5.json`
- Result:
  - regenerated to the same closure-honest state
  - `status=fail`
  - `missing_keys=["desktop_client"]`
  - completion audit remains external-only with unresolved tuple `avalonia:osx-arm64:macos`

Conclusion:
- From this Linux worker, there is no honest local step left that clears flagship readiness.
- The remaining work is fresh native macOS proof capture, bundle ingest, and readiness republish, not repo-local implementation.

Exact next action:
- Run `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh` on a native macOS host.
- Ingest the resulting bundle with `/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`.
- Republish readiness only after the new macOS receipt clears release-channel tuple coverage and flagship readiness verification.
