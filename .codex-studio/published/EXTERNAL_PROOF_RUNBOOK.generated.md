# External Proof Runbook

- generated_at: 2026-04-05T03:02:57Z
- unresolved_request_count: 4
- unresolved_hosts: macos, windows
- plan_generated_at: 2026-04-05T03:02:55Z
- release_channel_generated_at: 2026-04-05T03:02:54Z
- capture_deadline_hours: 24
- capture_deadline_utc: 2026-04-06T03:02:54Z

## Host: macos

- shell_hint: Run commands in a POSIX shell (bash/zsh) on the required host.
- request_count: 2
- tuples: avalonia:osx-arm64:macos, blazor-desktop:osx-arm64:macos

### Requested Tuples

- `avalonia:osx-arm64:macos`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `avalonia-osx-arm64-installer`
  installer_file: `chummer-avalonia-osx-arm64-installer.dmg`
  installer_relative_path: `files/chummer-avalonia-osx-arm64-installer.dmg`
  installer_sha256: `(missing)`
  public_route: `/downloads/install/avalonia-osx-arm64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`
  capture_deadline_utc: `2026-04-06T03:02:54Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-osx-arm64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg; fi`
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`
- `blazor-desktop:osx-arm64:macos`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `blazor-desktop-osx-arm64-installer`
  installer_file: `chummer-blazor-desktop-osx-arm64-installer.dmg`
  installer_relative_path: `files/chummer-blazor-desktop-osx-arm64-installer.dmg`
  installer_sha256: `(missing)`
  public_route: `/downloads/install/blazor-desktop-osx-arm64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json`
  capture_deadline_utc: `2026-04-06T03:02:54Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-osx-arm64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg; fi`
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg blazor-desktop osx-arm64 Chummer.Blazor.Desktop /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`

### Commands (Host Consolidated)

```bash
cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-osx-arm64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg; fi
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh
cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-osx-arm64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg; fi
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg blazor-desktop osx-arm64 Chummer.Blazor.Desktop /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
```

### Commands (Host Validation)

```bash
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json
```

## Host: windows

- shell_hint: Run canonical commands in Git Bash (or WSL bash). PowerShell wrappers are provided below when you need to stay in PowerShell.
- request_count: 2
- tuples: avalonia:win-x64:windows, blazor-desktop:win-x64:windows

### Requested Tuples

- `avalonia:win-x64:windows`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `avalonia-win-x64-installer`
  installer_file: `chummer-avalonia-win-x64-installer.exe`
  installer_relative_path: `files/chummer-avalonia-win-x64-installer.exe`
  installer_sha256: `(missing)`
  public_route: `/downloads/install/avalonia-win-x64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-avalonia-win-x64.receipt.json`
  capture_deadline_utc: `2026-04-06T03:02:54Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe; fi`
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`
- `blazor-desktop:win-x64:windows`
  required_proofs: `promoted_installer_artifact, startup_smoke_receipt`
  artifact_id: `blazor-desktop-win-x64-installer`
  installer_file: `chummer-blazor-desktop-win-x64-installer.exe`
  installer_relative_path: `files/chummer-blazor-desktop-win-x64-installer.exe`
  installer_sha256: `(missing)`
  public_route: `/downloads/install/blazor-desktop-win-x64-installer`
  startup_smoke_receipt: `startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json`
  capture_deadline_utc: `2026-04-06T03:02:54Z`
  capture_deadline_state: `pending`
  commands:
    - `cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe; fi`
    - `cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe blazor-desktop win-x64 Chummer.Blazor.Desktop.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke`
    - `cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh`

### Commands (Host Consolidated)

```bash
cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe; fi
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh
cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe; fi
cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe blazor-desktop win-x64 Chummer.Blazor.Desktop.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke
```

### Commands (Host Validation)

```bash
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe
cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json
```

### Commands (PowerShell Wrappers)

```powershell
bash -lc 'cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe; fi'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && mkdir -p /docker/chummercomplete/chummer6-ui/Docker/Downloads/files && if [ ! -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe ]; then curl -fL --retry 3 --retry-delay 2 "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-win-x64-installer" -o /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe; fi'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe blazor-desktop win-x64 Chummer.Blazor.Desktop.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke'
```

### Commands (PowerShell Validation Wrappers)

```powershell
bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-win-x64-installer.exe'
bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json'
```

## After Host Proof Capture

Run these commands after macOS/Windows proofs land to ingest receipts and republish release truth.

```bash
cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh
cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/materialize_public_release_channel.py --manifest /docker/chummercomplete/chummer6-ui/Docker/Downloads/RELEASE_CHANNEL.generated.json --downloads-dir /docker/chummercomplete/chummer6-ui/Docker/Downloads/files --startup-smoke-dir /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke --channel docker --version unpublished --published-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --output .codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/fleet && python3 scripts/materialize_status_plane.py --out .codex-studio/published/STATUS_PLANE.generated.yaml
cd /docker/fleet && python3 scripts/verify_status_plane_semantics.py --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml
cd /docker/fleet && python3 scripts/materialize_public_progress_report.py --out .codex-studio/published/PROGRESS_REPORT.generated.json --html-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.html --history-out .codex-studio/published/PROGRESS_HISTORY.generated.json --preview-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.json
cd /docker/fleet && python3 scripts/materialize_support_case_packets.py --out .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/fleet && python3 scripts/materialize_journey_gates.py --out .codex-studio/published/JOURNEY_GATES.generated.json --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml --progress-report .codex-studio/published/PROGRESS_REPORT.generated.json --progress-history .codex-studio/published/PROGRESS_HISTORY.generated.json --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json
cd /docker/fleet && python3 scripts/materialize_external_proof_runbook.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --out .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md
cd /docker/fleet && python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json
cd /docker/fleet && python3 scripts/materialize_flagship_product_readiness.py --out .codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json
cd /docker/chummercomplete/chummer-design && python3 scripts/ai/materialize_weekly_product_pulse_snapshot.py --out products/chummer/WEEKLY_PRODUCT_PULSE.generated.json
cd /docker/fleet && python3 scripts/chummer_design_supervisor.py status >/dev/null
```
