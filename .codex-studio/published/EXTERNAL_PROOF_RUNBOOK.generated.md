# External Proof Runbook

- generated_at: 2026-05-05T16:12:36Z
- unresolved_request_count: 0
- unresolved_hosts: (none)
- plan_generated_at: 2026-05-05T16:12:15Z
- release_channel_generated_at: 2026-05-05T15:55:24Z
- capture_deadline_hours: 24
- capture_deadline_utc: 2026-05-06T15:55:24Z

## Prerequisites

- Run each host section on the matching native host (`macos` on macOS, `windows` on Windows).
- Provide signed-in download credentials before capture when public routes are account-gated.
- Supported auth inputs: `CHUMMER_EXTERNAL_PROOF_AUTH_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_JAR`.
- Set `CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1` only when install routes are intentionally guest-readable.
- Optional base URL override: `CHUMMER_EXTERNAL_PROOF_BASE_URL` (default `${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}`).

## Generated Command Files

- commands_dir: `/docker/fleet/.codex-studio/published/external-proof-commands`
- command_bundle_sha256: `aeb158c27e9135ba38313a6a988012c27982cf11ae18c6389bb9a2eef5575102`
- command_bundle_file_count: 26
- host `linux`
  preflight_script: `/docker/fleet/.codex-studio/published/external-proof-commands/preflight-linux-proof.sh`
  capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-linux-proof.sh`
  validation_script: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-linux-proof.sh`
  bundle_script: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-linux-proof.sh`
  ingest_script: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-linux-proof-bundle.sh`
  host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-linux-proof-lane.sh`
  command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/linux-proof-command-pack.tgz`
  command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/linux-proof-command-pack.tgz.sha256`
  command_pack_sha256: `8fdbd228a9716fc74a48564c65c89a83c412964bb5b094fab67723321eee9b3f`
- host `macos`
  preflight_script: `/docker/fleet/.codex-studio/published/external-proof-commands/preflight-macos-proof.sh`
  capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-macos-proof.sh`
  validation_script: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-macos-proof.sh`
  bundle_script: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-macos-proof.sh`
  ingest_script: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-macos-proof-bundle.sh`
  host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`
  command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-command-pack.tgz`
  command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-command-pack.tgz.sha256`
  command_pack_sha256: `7bcc874da9d9907195e3c03edeb847c78df9518a8181a0d12b4ed52b6c40f9be`
- host `windows`
  preflight_script: `/docker/fleet/.codex-studio/published/external-proof-commands/preflight-windows-proof.sh`
  capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-windows-proof.sh`
  validation_script: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-windows-proof.sh`
  bundle_script: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-windows-proof.sh`
  ingest_script: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-windows-proof-bundle.sh`
  host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-windows-proof-lane.sh`
  command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz`
  command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz.sha256`
  command_pack_sha256: `efe98a98fa760374ce4cc7e71e0529e8363312b9af33174682de6732537b8e74`
  preflight_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/preflight-windows-proof.ps1`
  capture_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/capture-windows-proof.ps1`
  validation_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/validate-windows-proof.ps1`
  bundle_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/bundle-windows-proof.ps1`
  ingest_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/ingest-windows-proof-bundle.ps1`
  host_lane_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/run-windows-proof-lane.ps1`
- post_capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/republish-after-host-proof.sh`
- finalize_script: `/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`

## Retained Host Lanes

These command bundles stay materialized even with zero backlog so native-host proof capture can resume without rebuilding the lane.

### Host: linux

- shell_hint: Run commands in a POSIX shell (bash/zsh) on the required host.
- request_count: 0
- tuples: (none)
- host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-linux-proof-lane.sh`
- retained_bundle_archive_path: `/docker/fleet/.codex-studio/published/external-proof-commands/linux-proof-bundle.tgz`
- retained_bundle_archive_present: `true`
- retained_bundle_directory_path: `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/linux`
- retained_bundle_directory_present: `true`
- command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/linux-proof-command-pack.tgz`
- command_pack_present: `true`
- command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/linux-proof-command-pack.tgz.sha256`
- command_pack_sha256: `8fdbd228a9716fc74a48564c65c89a83c412964bb5b094fab67723321eee9b3f`

### Host: macos

- shell_hint: Run commands in a POSIX shell (bash/zsh) on the required host.
- platform_hint: macOS proofs require `hdiutil` on the proof host.
- request_count: 0
- tuples: (none)
- host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-macos-proof-lane.sh`
- retained_bundle_archive_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-bundle.tgz`
- retained_bundle_archive_present: `true`
- retained_bundle_directory_path: `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/macos`
- retained_bundle_directory_present: `true`
- command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-command-pack.tgz`
- command_pack_present: `true`
- command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/macos-proof-command-pack.tgz.sha256`
- command_pack_sha256: `7bcc874da9d9907195e3c03edeb847c78df9518a8181a0d12b4ed52b6c40f9be`

### Host: windows

- shell_hint: Run canonical commands in Git Bash (or WSL bash). PowerShell wrappers are provided below when you need to stay in PowerShell.
- platform_hint: Windows proofs require `powershell.exe` or `pwsh` on the proof host.
- request_count: 0
- tuples: (none)
- host_lane_script: `/docker/fleet/.codex-studio/published/external-proof-commands/run-windows-proof-lane.sh`
- host_lane_powershell: `/docker/fleet/.codex-studio/published/external-proof-commands/run-windows-proof-lane.ps1`
- retained_bundle_archive_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-bundle.tgz`
- retained_bundle_archive_present: `true`
- retained_bundle_directory_path: `/docker/fleet/.codex-studio/published/external-proof-commands/host-proof-bundles/windows`
- retained_bundle_directory_present: `true`
- command_pack_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz`
- command_pack_present: `true`
- command_pack_sha256_path: `/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz.sha256`
- command_pack_sha256: `efe98a98fa760374ce4cc7e71e0529e8363312b9af33174682de6732537b8e74`

## Resume Commands

Use these exact retained entrypoints to reopen native-host capture without rebuilding the command bundle.

### Resume Host Lane: linux

```bash
cd /docker/fleet/.codex-studio/published/external-proof-commands
./preflight-linux-proof.sh
./capture-linux-proof.sh
./validate-linux-proof.sh
./bundle-linux-proof.sh
```

### Resume Host Lane: macos

```bash
cd /docker/fleet/.codex-studio/published/external-proof-commands
./preflight-macos-proof.sh
./capture-macos-proof.sh
./validate-macos-proof.sh
./bundle-macos-proof.sh
```

### Resume Host Lane: windows

```bash
cd /docker/fleet/.codex-studio/published/external-proof-commands
./preflight-windows-proof.sh
./capture-windows-proof.sh
./validate-windows-proof.sh
./bundle-windows-proof.sh
```

### Resume Host Lane (PowerShell): windows

```powershell
bash -lc 'set -euo pipefail
cd /docker/fleet/.codex-studio/published/external-proof-commands
./preflight-windows-proof.sh
./capture-windows-proof.sh
./validate-windows-proof.sh
./bundle-windows-proof.sh'
```

## After Host Proof Capture

Run these retained commands after a host lane succeeds to validate receipts, ingest bundles, and republish release truth.

```bash
/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh
```

```bash
cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/materialize_public_release_channel.py --manifest /docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads/RELEASE_CHANNEL.generated.json --downloads-dir /docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads/files --startup-smoke-dir /docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads/startup-smoke --channel docker --version unpublished --published-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --output .codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/verify_public_release_channel.py /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/fleet && python3 scripts/materialize_status_plane.py --out .codex-studio/published/STATUS_PLANE.generated.yaml
cd /docker/fleet && python3 scripts/verify_status_plane_semantics.py --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml
cd /docker/fleet && python3 scripts/materialize_public_progress_report.py --out .codex-studio/published/PROGRESS_REPORT.generated.json --html-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.html --history-out .codex-studio/published/PROGRESS_HISTORY.generated.json --preview-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.json
cd /docker/fleet && python3 scripts/materialize_support_case_packets.py --out .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/fleet && python3 scripts/materialize_journey_gates.py --out .codex-studio/published/JOURNEY_GATES.generated.json --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml --progress-report .codex-studio/published/PROGRESS_REPORT.generated.json --progress-history .codex-studio/published/PROGRESS_HISTORY.generated.json --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
cd /docker/fleet && python3 scripts/materialize_external_proof_runbook.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates /docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --out .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md
cd /docker/fleet && python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir .codex-studio/published/external-proof-commands
cd /docker/fleet && python3 scripts/materialize_flagship_product_readiness.py --out .codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json --mirror-out /docker/fleet/.codex-design/product/FLAGSHIP_PRODUCT_READINESS.generated.json
cd /docker/chummercomplete/chummer-design && python3 scripts/ai/materialize_weekly_product_pulse_snapshot.py --out products/chummer/WEEKLY_PRODUCT_PULSE.generated.json
```

No unresolved external-proof requests are currently queued.
