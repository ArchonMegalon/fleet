# External Proof Runbook

- generated_at: 2026-04-05T01:02:22Z
- unresolved_request_count: 4
- unresolved_hosts: macos, windows
- plan_generated_at: 2026-04-05T01:02:21Z
- release_channel_generated_at: 2026-04-05T01:01:17Z
- capture_deadline_hours: 24
- capture_deadline_utc: 2026-04-06T01:01:17Z

## Host: macos

- request_count: 2
- tuples: avalonia:osx-arm64:macos, blazor-desktop:osx-arm64:macos

### Requested Tuples

- `avalonia:osx-arm64:macos`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `avalonia-osx-arm64-installer`
  installer_file: `chummer-avalonia-osx-arm64-installer.dmg`
  installer_relative_path: `files/chummer-avalonia-osx-arm64-installer.dmg`
  public_route: `/downloads/install/avalonia-osx-arm64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
  capture_deadline_utc: `2026-04-06T01:01:17Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`
- `blazor-desktop:osx-arm64:macos`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `blazor-desktop-osx-arm64-installer`
  installer_file: `chummer-blazor-desktop-osx-arm64-installer.dmg`
  installer_relative_path: `files/chummer-blazor-desktop-osx-arm64-installer.dmg`
  public_route: `/downloads/install/blazor-desktop-osx-arm64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json`
  capture_deadline_utc: `2026-04-06T01:01:17Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg blazor-desktop osx-arm64 Chummer.Blazor.Desktop /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`

### Commands (Host Consolidated)

```bash
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg blazor-desktop osx-arm64 Chummer.Blazor.Desktop /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
```

## Host: windows

- request_count: 2
- tuples: avalonia:win-x64:windows, blazor-desktop:win-x64:windows

### Requested Tuples

- `avalonia:win-x64:windows`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `avalonia-win-x64-installer`
  installer_file: `chummer-avalonia-win-x64-installer.exe`
  installer_relative_path: `files/chummer-avalonia-win-x64-installer.exe`
  public_route: `/downloads/install/avalonia-win-x64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-avalonia-win-x64.receipt.json`
  capture_deadline_utc: `2026-04-06T01:01:17Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`
- `blazor-desktop:win-x64:windows`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `blazor-desktop-win-x64-installer`
  installer_file: `chummer-blazor-desktop-win-x64-installer.exe`
  installer_relative_path: `files/chummer-blazor-desktop-win-x64-installer.exe`
  public_route: `/downloads/install/blazor-desktop-win-x64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json`
  capture_deadline_utc: `2026-04-06T01:01:17Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe blazor-desktop win-x64 Chummer.Blazor.Desktop.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`

### Commands (Host Consolidated)

```bash
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe blazor-desktop win-x64 Chummer.Blazor.Desktop.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
```

## After Host Proof Capture

Run these commands after macOS/Windows proofs land to ingest receipts and republish release truth.

```bash
cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh
cd /docker/fleet && python3 scripts/materialize_support_case_packets.py --out .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
cd /docker/fleet && python3 scripts/materialize_journey_gates.py --out .codex-studio/published/JOURNEY_GATES.generated.json --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml --progress-report .codex-studio/published/PROGRESS_REPORT.generated.json --progress-history .codex-studio/published/PROGRESS_HISTORY.generated.json --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
cd /docker/fleet && python3 scripts/materialize_external_proof_runbook.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --out .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md
cd /docker/fleet && python3 scripts/materialize_flagship_product_readiness.py --out .codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json
cd /docker/fleet && python3 scripts/materialize_public_progress_report.py --out .codex-studio/published/PROGRESS_REPORT.generated.json --html-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.html --history-out .codex-studio/published/PROGRESS_HISTORY.generated.json --preview-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.json
cd /docker/chummercomplete/chummer-design && python3 scripts/ai/materialize_weekly_product_pulse_snapshot.py --out products/chummer/WEEKLY_PRODUCT_PULSE.generated.json
cd /docker/fleet && python3 scripts/chummer_design_supervisor.py status >/dev/null
```
